from dataclasses import dataclass, asdict
import time, json
from typing import Callable, Optional, Dict, Any
from .pricing import DEFAULT_PRICING, estimate_cost

def _get_dynamic_pricing():
    try:
        from .price_fetcher import get_dynamic_pricing
        return get_dynamic_pricing()
    except:
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

class CostProfiler:
    def __init__(self, pricing: Optional[Dict]=None, sink_path="llm_costs.jsonl",
                 pricing_source="builtin", price_adjustment=1.0):
        base = DEFAULT_PRICING.copy()
        dyn = _get_dynamic_pricing() if pricing_source=="dynamic" else {}
        merged = {**base, **dyn, **(pricing or {})}

        self.pricing = merged
        self.price_adjustment = float(price_adjustment)
        self.sink_path = sink_path
        open(self.sink_path, "a").close()

    def _estimate_cost(self, model, p, c):
        return round(estimate_cost(self.pricing, model, p, c) * self.price_adjustment, 10)

    def record_call(self, model, p, c, latency, tags=None):
        total = p + c
        cost = self._estimate_cost(model, p, c)
        rec = CallRecord(time.time(), model, p, c, total, latency, cost, tags or {})
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
