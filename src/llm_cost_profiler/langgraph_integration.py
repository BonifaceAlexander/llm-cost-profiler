"""
Per-step cost/latency attribution for LangGraph (and similar node-based
agent frameworks).

Why this exists
----------------
llm-cost-profiler's core decorator (`profile_llm_call`) and callback
(`LangChainCallback`) tell you the total cost of a run. They don't tell
you *which part of the agent* spent that money - was it the retrieval
step, the planning step, or a runaway tool-call loop?

This module answers that by wrapping each graph node with `profile_node`.
While a node is executing, any LLM call made inside it - whether tracked
manually or via `LangGraphCostCallback` - is automatically tagged with
that node's name, using a contextvar so you don't have to pass step
names around by hand.

Usage
-----
    from llm_cost_profiler import CostProfiler
    from llm_cost_profiler.langgraph_integration import (
        profile_node, LangGraphCostCallback,
    )

    prof = CostProfiler(sink_path="agent_costs.jsonl")
    callback = LangGraphCostCallback(prof)

    @profile_node("retrieve_docs", profiler=prof)
    def retrieve_docs(state):
        ...
        return state

    @profile_node("generate_answer", profiler=prof)
    def generate_answer(state):
        response = llm.invoke(state["query"], config={"callbacks": [callback]})
        return {"answer": response.content}

    graph = StateGraph(State)
    graph.add_node("retrieve_docs", retrieve_docs)
    graph.add_node("generate_answer", generate_answer)
    ...
    compiled = graph.compile()
    compiled.invoke(initial_state, config={"callbacks": [callback]})

    print(prof.report_by_step())
    # {'steps': {'generate_answer': {...cost/latency...},
    #            'retrieve_docs':  {...cost/latency...}}, ...}

Notes
-----
- Nodes are wrapped *before* being added to the graph. We deliberately
  do not reach into `CompiledStateGraph`/`PregelNode` internals to
  auto-instrument an already-built graph, since those are private
  APIs that change across LangGraph versions. Wrapping at definition
  time is a few extra lines per node but is stable across versions.
- `profile_node` works for both sync and async node functions.
"""

import time
import inspect
from typing import Optional

from .context import current_step
from .profiler import CostProfiler
from .wrappers import LangChainCallback, HAS_LC


def profile_node(step_name: str, profiler: Optional[CostProfiler] = None):
    """Wrap a LangGraph node function so LLM calls inside it are tagged
    with `step_name`, and (if `profiler` is given) the node's own
    wall-clock time is logged as a zero-cost record.

    The zero-cost "node" record matters for steps that don't call an
    LLM at all (retrieval, parsing, routing/branching logic) - without
    it, those steps would be invisible in report_by_step() even though
    they can dominate latency.
    """

    def deco(fn):
        is_async = inspect.iscoroutinefunction(fn)

        def _log_node_latency(latency):
            if profiler is not None:
                profiler.record_call(
                    model="__node__",
                    p=0,
                    c=0,
                    latency=latency,
                    tags={"node_only": True},
                    step=step_name,
                )

        if is_async:
            async def awrapper(*args, **kwargs):
                token = current_step.set(step_name)
                start = time.time()
                try:
                    return await fn(*args, **kwargs)
                finally:
                    _log_node_latency(time.time() - start)
                    current_step.reset(token)
            return awrapper

        def wrapper(*args, **kwargs):
            token = current_step.set(step_name)
            start = time.time()
            try:
                return fn(*args, **kwargs)
            finally:
                _log_node_latency(time.time() - start)
                current_step.reset(token)
        return wrapper

    return deco


class LangGraphCostCallback(LangChainCallback):
    """LangChain callback that behaves like `LangChainCallback` but also
    tags each record with the currently-executing step (as set by
    `profile_node`). Register it once per graph invoke - it will
    correctly attribute cost to whichever node is active when each
    LLM call happens, since node execution and the contextvar are
    tied together by `profile_node`.
    """

    def on_llm_end(self, response, **kwargs):
        if not HAS_LC:
            return
        try:
            out = getattr(response, "llm_output", {}) or response.get("llm_output", {})
            usage = out.get("tokens", {}) or out.get("usage", {})
            p = usage.get("prompt_tokens") or usage.get("input_tokens") or 0
            c = usage.get("completion_tokens") or usage.get("output_tokens") or 0
            model = kwargs.get("model_name") or out.get("model") or "unknown"
            self.profiler.record_call(
                model, p, c, 0.0,
                tags={"langchain": True},
                step=current_step.get(),
            )
        except Exception as e:
            print("[llm-cost-profiler] LangGraphCostCallback failed:", e)
