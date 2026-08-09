"""
Per-step cost attribution for a real LangGraph agent.

Run with:
    python examples/langgraph_step_attribution.py

This builds a 3-node agent (retrieve -> generate -> critique) and shows
report_by_step() pinpointing which node is actually driving cost -
something report_summary() alone (grouped by model) can't tell you.
"""
import time
from typing import TypedDict

from langgraph.graph import StateGraph, END

from llm_cost_profiler import CostProfiler, profile_llm_call
from llm_cost_profiler.langgraph_integration import profile_node


class AgentState(TypedDict):
    query: str
    docs: str
    answer: str
    critique: str


prof = CostProfiler(sink_path="langgraph_costs.jsonl")


def fake_llm_response(prompt_tokens, completion_tokens):
    return {"usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens}}


@profile_llm_call(
    prof,
    model_key_getter=lambda a, k: k.get("model", "gpt-4.1"),
    token_counts_getter=lambda r: (r["usage"]["prompt_tokens"], r["usage"]["completion_tokens"]),
)
def call_llm(prompt, model="gpt-4.1", prompt_tokens=500, completion_tokens=200):
    time.sleep(0.01)  # simulate network latency
    return fake_llm_response(prompt_tokens, completion_tokens)


@profile_node("retrieve_docs", profiler=prof)
def retrieve_docs(state: AgentState) -> dict:
    time.sleep(0.02)  # e.g. a vector DB lookup - no LLM call, still worth seeing
    return {"docs": f"[retrieved context for: {state['query']}]"}


@profile_node("generate_answer", profiler=prof)
def generate_answer(state: AgentState) -> dict:
    call_llm(state["query"], model="gpt-4.1", prompt_tokens=1200, completion_tokens=400)
    return {"answer": "a generated answer using the retrieved docs"}


@profile_node("critique_answer", profiler=prof)
def critique_answer(state: AgentState) -> dict:
    call_llm(state["answer"], model="gpt-3.5-turbo", prompt_tokens=300, completion_tokens=100)
    return {"critique": "looks accurate and well-grounded"}


graph = StateGraph(AgentState)
graph.add_node("retrieve_docs", retrieve_docs)
graph.add_node("generate_answer", generate_answer)
graph.add_node("critique_answer", critique_answer)
graph.set_entry_point("retrieve_docs")
graph.add_edge("retrieve_docs", "generate_answer")
graph.add_edge("generate_answer", "critique_answer")
graph.add_edge("critique_answer", END)

compiled = graph.compile()
compiled.invoke({"query": "What is agentic RAG?", "docs": "", "answer": "", "critique": ""})

import json
print("Per-step breakdown (sorted by cost, most expensive first):\n")
print(json.dumps(prof.report_by_step(), indent=2))
