# llm-cost-profiler

[![PyPI version](https://img.shields.io/pypi/v/llm-cost-profiler?label=PyPI)](https://pypi.org/project/llm-cost-profiler/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

A lightweight, framework-agnostic library for tracking **LLM token usage, cost, and latency** across OpenAI, LangChain, LangGraph, FastAPI, batch jobs, and any custom Python workflow.

It helps teams bring **visibility**, **observability**, and **cost analytics** into any LLM-powered system with almost zero code changes.

## Contents

- [Overview](#overview)
- [Features](#features)
- [Installation](#installation)
- [Quick start](#quick-start)
- [Per-step cost attribution (LangGraph)](#per-step-cost-attribution-langgraph)
- [litellm-backed pricing (hundreds of models)](#litellm-backed-pricing-hundreds-of-models)
- [Local dashboard](#local-dashboard)
- [Examples](#examples)
- [How the decorator works](#how-the-decorator-works)
- [Configuration](#configuration)
- [Development](#development)
- [Contributing](#contributing)
- [License](#license)

## Overview

`llm-cost-profiler` is a small, dependency-light Python library for tracking LLM usage, latency, and estimated cost across different model providers. It provides simple instrumentation primitives (manual recording and a decorator), JSONL logging for audit and analysis, optional dynamic pricing lookups, and per-agent-step cost attribution for LangGraph pipelines.

Perfect for developers building RAG systems, agents, batch inference jobs, Streamlit apps, FastAPI services, and more.

## Features

- Token usage (prompt & completion) tracking
- Model-specific cost estimation
- Latency & response time tracking
- **Per-agent-step cost attribution for LangGraph** — see which node in your pipeline is actually driving cost, not just which model
- **litellm-backed pricing** for hundreds of models across providers, with automatic fallback
- **Local Streamlit dashboard** — cost/latency by step and model, budget alerts
- JSONL logging sink for audits & dashboards
- Simple decorator to profile function calls
- Dynamic pricing (optional) with safe fallbacks
- Minimal dependencies, zero required dependencies on AI frameworks
- Works with OpenAI, LangChain, LangGraph, custom clients, batch jobs, APIs
- Built for production observability (text logs → data lakes)

## Installation

Install from PyPI:

```bash
pip install llm-cost-profiler
```

Optional extras, installable individually or combined:

```bash
pip install llm-cost-profiler[langgraph]   # per-step attribution for LangGraph
pip install llm-cost-profiler[litellm]     # pricing for hundreds of models via litellm
pip install llm-cost-profiler[dashboard]   # local Streamlit dashboard
pip install llm-cost-profiler[all]         # everything above
```

## Quick start

```python
from llm_cost_profiler import CostProfiler, profile_llm_call
from openai import OpenAI

client = OpenAI(api_key="YOUR_KEY")
prof = CostProfiler("local_costs.jsonl")

@profile_llm_call(
    prof,
    model_key_getter=lambda a, k: k.get("model", "gpt-4o"),
    token_counts_getter=lambda r: (r["usage"]["prompt_tokens"], r["usage"]["completion_tokens"]),
)
def ask(prompt, model="gpt-4o"):
    return client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )

ask("Explain LLM observability like I'm 5")
print(prof.report_summary())
```

## Per-step cost attribution (LangGraph)

Knowing your agent spent $12 today doesn't tell you *why*. `report_summary()` groups cost by model — useful, but not enough once you have multiple LLM calls across multiple steps of an agent. `report_by_step()` groups by which **node** in your agent actually spent it, so you can answer "which part of my agent is burning the budget?" directly.

```python
from llm_cost_profiler import CostProfiler, profile_llm_call
from llm_cost_profiler.langgraph_integration import profile_node

prof = CostProfiler(sink_path="agent_costs.jsonl")

@profile_llm_call(
    prof,
    model_key_getter=lambda a, k: k.get("model", "gpt-4.1"),
    token_counts_getter=lambda r: (r["usage"]["prompt_tokens"], r["usage"]["completion_tokens"]),
)
def call_llm(prompt, model="gpt-4.1"):
    ...

@profile_node("retrieve_docs", profiler=prof)
def retrieve_docs(state):
    ...  # any LLM calls made in here are auto-tagged step="retrieve_docs"
    return state

@profile_node("generate_answer", profiler=prof)
def generate_answer(state):
    call_llm(state["query"], model="gpt-4.1")
    return state

# ... build your StateGraph with these wrapped node functions as usual ...

print(prof.report_by_step())
# {"steps": {"generate_answer": {"cost_usd": 0.12, ...},
#            "retrieve_docs":   {"cost_usd": 0.0,  ...}}, ...}
# sorted with the most expensive step first
```

You don't need to change how you call your LLM client, and nodes with no LLM call at all (retrieval, routing, parsing) still show up with their latency, so slow-but-free steps aren't invisible either.

Nodes are wrapped before being added to the graph, rather than instrumented after `.compile()` — LangGraph's compiled internals are private APIs that change across versions, so wrapping at definition time keeps this stable regardless of which LangGraph version you're on.

See [`examples/langgraph_step_attribution.py`](examples/langgraph_step_attribution.py) for a full runnable example against a real `StateGraph`.

## litellm-backed pricing (hundreds of models)

The builtin pricing table only knows a handful of models. For broader,
better-maintained coverage, use `pricing_source="litellm"` to price
calls using [litellm](https://github.com/BerriAI/litellm)'s pricing
table, which covers hundreds of models across OpenAI, Anthropic,
Google, Cohere, Azure, Bedrock, and more.

```python
from llm_cost_profiler import CostProfiler

prof = CostProfiler("costs.jsonl", pricing_source="litellm")

# OpenAI models work with bare names:
prof.record_call("gpt-4o", 1000, 500, latency=0.02)

# Other providers: use the explicit "provider/model" form - this is
# the reliable pattern. A bare non-OpenAI name sometimes works and
# sometimes doesn't (inconsistent in litellm itself depending on the
# exact model string), so always prefix to be safe:
prof.record_call("anthropic/claude-sonnet-4-5-20250929", 1000, 500, latency=0.02)
```

If litellm doesn't recognize a model (unmapped, or a very recent
release litellm hasn't added yet), `CostProfiler` automatically falls
back to the builtin pricing table for that call - you'll never get a
crash or a silent $0 cost from an unrecognized model.

Install with:
```bash
pip install llm-cost-profiler[litellm]
```

See [`examples/litellm_pricing_example.py`](examples/litellm_pricing_example.py).

## Local dashboard

View cost, tokens, and latency - overall and broken down by step and
model - in a local Streamlit dashboard reading directly from your
JSONL log:

```bash
pip install llm-cost-profiler[dashboard]
llm-cost-profiler dashboard --sink agent_costs.jsonl
```

Optional flags:
- `--budget 5.00` — shows a warning banner if total logged cost exceeds this
- `--port 8765` — serve on a specific port
- `--headless` — don't try to open a browser (useful on a remote server)

The dashboard shows total cost/calls/tokens, cost by step, cost by
model, cumulative cost over time, and average latency by step - the
same `report_by_step()` / `report_summary()` data as the Python API,
in a browsable view you can leave open while developing.

## Examples

All runnable examples are inside the [`examples/`](examples/) directory. Run any of them with:

```bash
python examples/<file>.py
```

**Core**
| File | What it shows |
|---|---|
| `example_basic_profiler.py` | Minimal fake call + cost |
| `example_multiple_calls.py` | Tags and multiple calls |
| `example_jsonl_logging.py` | JSONL logs + reading back |
| `example_model_price_override.py` | Override the pricing table |

**Integrations**
| File | What it shows |
|---|---|
| `openai_integration.py` | Real OpenAI client usage |
| `langchain_integration.py` | Decorator wrapper over LangChain |
| `langgraph_step_attribution.py` | Per-node cost attribution over a real LangGraph `StateGraph` |
| `litellm_pricing_example.py` | Pricing calls with litellm's maintained pricing table |
| `fastapi_server.py` | API endpoint that tracks cost per request |
| `batch_job.py` | Batch summarization worker |

## How the decorator works

```python
@profile_llm_call(
    prof,
    model_key_getter=lambda args, kwargs: kwargs.get("model"),
    token_counts_getter=lambda resp: (
        resp["usage"]["prompt_tokens"],
        resp["usage"]["completion_tokens"],
    ),
)
def llm_call(...):
    ...
```

The decorator automatically captures:

- model name
- prompt & completion tokens
- execution time
- estimated cost
- any custom tags you pass via `tags_getter`
- the currently-executing agent step, if called from inside a `profile_node`-wrapped function

...and logs it as JSONL.

## Configuration

`llm-cost-profiler` doesn't require any environment variables to work — `CostProfiler(sink_path=...)` and the built-in pricing table are enough out of the box.

Two optional environment variables affect the *dynamic pricing cache* (used only if you construct `CostProfiler(pricing_source="dynamic")`):

| Variable | Default | Purpose |
|---|---|---|
| `LLM_PRICING_CACHE` | `.llm_pricing_cache.json` | Path to the local cache file for fetched pricing data |
| `LLM_PRICING_TTL_SECONDS` | `86400` (24h) | How long cached pricing data is considered fresh |

Any API keys for the LLM provider you're calling (e.g. `OPENAI_API_KEY`) are your own client's responsibility — `llm-cost-profiler` never reads or requires them, since it only wraps your existing calls rather than making any itself.

## Development

Clone the repo and use a virtualenv:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
pytest -q
```

For LangGraph-related development/tests:

```bash
pip install -e .[langgraph]
```

## Contributing

Contributions welcome — open issues and PRs. Please follow the project's existing code style and add tests for new behavior.

## License

MIT © Boniface Alexander
