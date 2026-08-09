from dataclasses import dataclass, asdict
import time, json
from typing import Callable, Optional, Dict, Any
from .pricing import DEFAULT_PRICING, estimate_cost
from .context import current_step
from .litellm_pricing import estimate_cost_litellm

def _get_dynamic_pricing():
    try:
        from .price_fetcher import get_dynamic_pricing
        return get_dynamic_pricing()
    except Exception:
        return {}

@dataclass
class CallRecord:
    timestamp: float
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_s: float
    cost_usd: float
    tags: Dict[str, Any]
    step: Optional[str] = None

class CostProfiler:
    def __init__(self, sink_path="llm_costs.jsonl", pricing: Optional[Dict]=None,
                 pricing_source="builtin", price_adjustment=1.0):
        """
        pricing_source:
          - "builtin": use the small hardcoded DEFAULT_PRICING table
          - "dynamic": builtin table + best-effort fetched/cached pricing
          - "litellm": use litellm's maintained pricing table (covers
            hundreds of models) for each call; if litellm doesn't
            recognize a given model, falls back to the builtin table
            for that call only (requires `pip install litellm`)
        """
        base = DEFAULT_PRICING.copy()
        dyn = _get_dynamic_pricing() if pricing_source=="dynamic" else {}
        merged = {**base, **dyn, **(pricing or {})}

        self.pricing = merged
        self.pricing_source = pricing_source
        self.price_adjustment = float(price_adjustment)
        self.sink_path = sink_path
        open(self.sink_path, "a").close()

    def _estimate_cost(self, model, p, c):
        if self.pricing_source == "litellm":
            litellm_cost = estimate_cost_litellm(model, p, c)
            if litellm_cost is not None:
                return round(litellm_cost * self.price_adjustment, 10)
            # litellm didn't recognize this model - fall back to the
            # builtin table below rather than crash or return $0.
        return round(estimate_cost(self.pricing, model, p, c) * self.price_adjustment, 10)

    def record_call(self, model, p, c, latency, tags=None, step=None):
        total = p + c
        cost = self._estimate_cost(model, p, c)
        # If caller didn't explicitly pass a step, fall back to whatever
        # profile_node() has set as "currently executing" via contextvar.
        # This is what lets a plain @profile_llm_call-decorated function
        # get correctly attributed when it's called from inside a node
        # wrapped with @profile_node(...), with zero extra code.
        if step is None:
            step = current_step.get()
        rec = CallRecord(time.time(), model, p, c, total, latency, cost, tags or {}, step)
        with open(self.sink_path, "a") as f:
            f.write(json.dumps(asdict(rec)) + "\n")
        return rec

    def report_summary(self):
        totals = {}
        count = 0
        total_cost = 0

        with open(self.sink_path) as f:
            for line in f:
                if not line.strip(): continue
                r = json.loads(line)
                m = r["model"]
                totals.setdefault(m, {"calls":0,"prompt_tokens":0,"completion_tokens":0,"cost":0.0,"latency":0.0})
                totals[m]["calls"] += 1
                totals[m]["prompt_tokens"] += r["prompt_tokens"]
                totals[m]["completion_tokens"] += r["completion_tokens"]
                totals[m]["cost"] += r["cost_usd"]
                totals[m]["latency"] += r["latency_s"]
                total_cost += r["cost_usd"]
                count += 1

        for m in totals:
            totals[m]["avg_latency_s"] = totals[m]["latency"] / max(1, totals[m]["calls"])
            totals[m].pop("latency")

        return {"models": totals, "meta": {"total_calls":count, "total_cost_usd":round(total_cost,6)}}

    def report_by_step(self):
        """Aggregate cost, tokens, and latency per agent/graph step (node).

        Records with no step set are grouped under 'unattributed'. This is
        the key view for multi-agent / LangGraph pipelines: it answers
        'which step in my agent is actually costing me money and time?'
        instead of only showing totals per model.
        """
        steps = {}
        total_cost = 0
        count = 0

        with open(self.sink_path) as f:
            for line in f:
                if not line.strip(): continue
                r = json.loads(line)
                step = r.get("step") or "unattributed"
                s = steps.setdefault(step, {
                    "calls": 0, "prompt_tokens": 0, "completion_tokens": 0,
                    "cost_usd": 0.0, "latency_s": 0.0,
                })
                s["calls"] += 1
                s["prompt_tokens"] += r["prompt_tokens"]
                s["completion_tokens"] += r["completion_tokens"]
                s["cost_usd"] += r["cost_usd"]
                s["latency_s"] += r["latency_s"]
                total_cost += r["cost_usd"]
                count += 1

        for s in steps.values():
            s["avg_latency_s"] = round(s["latency_s"] / max(1, s["calls"]), 6)
            s["cost_usd"] = round(s["cost_usd"], 6)

        # sort steps by cost, highest first, so the worst offender is first
        ordered = dict(sorted(steps.items(), key=lambda kv: kv[1]["cost_usd"], reverse=True))

        return {"steps": ordered, "meta": {"total_calls": count, "total_cost_usd": round(total_cost, 6)}}

def profile_llm_call(profiler, model_key_getter, token_counts_getter, tags_getter=None):
    def deco(fn):
        def wrapper(*args, **kwargs):
            start = time.time()
            resp = fn(*args, **kwargs)
            lat = time.time() - start
            try:
                model = model_key_getter(args, kwargs)
                p,c = token_counts_getter(resp)
                tags = tags_getter(args, kwargs, resp) if tags_getter else {}
                profiler.record_call(model, p or 0, c or 0, lat, tags)
            except Exception as e:
                print("[llm-cost-profiler] profiling failed:", e)
            return resp
        return wrapper
    return deco
