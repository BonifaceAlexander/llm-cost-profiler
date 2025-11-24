# llm-cost-profiler


[![PyPI version](https://img.shields.io/pypi/v/llm-cost-profiler?label=PyPI)](https://pypi.org/project/llm-cost-profiler/0.1.2/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

A lightweight, framework-agnostic library for tracking **LLM token usage, cost, and latency** across OpenAI, LangChain, FastAPI, batch jobs, and any custom Python workflow.

It helps teams bring **visibility**, **observability**, and **cost analytics** into any LLM-powered system with almost zero code changes.


## Overview

`llm-cost-profiler` is a small, dependency-light Python library for tracking LLM usage, latency and estimated cost across different model providers. It provides simple instrumentation primitives (manual recording and a decorator), JSONL logging for audit and analysis, and optional dynamic pricing lookups.

Perfect for developers building RAG systems, agents, batch inference jobs, Streamlit apps, FastAPI services, and more.

## Features
- Token usage (prompt & completion) tracking
- Model-specific cost estimation
- Latency & response time tracking
- JSONL logging sink for audits & dashboards
- Simple decorator to profile function calls
- Dynamic pricing (optional) with safe fallbacks
- Minimal dependencies
- Zero dependencies on AI frameworks  
- Works with OpenAI, LangChain, custom clients, batch jobs, APIs  
- Built for production observability (text logs → data lakes)

## Installation

Install from PyPI:

```bash
pip install llm-cost-profiler

## QUICK START

from llm_cost_profiler import CostProfiler, profile_llm_call
from openai import OpenAI

client = OpenAI(api_key="YOUR_KEY")
prof = CostProfiler("local_costs.jsonl")

@profile_llm_call(
    prof,
    model_getter=lambda a,k: k.get("model", "gpt-4o"),
    token_getter=lambda r: (r["usage"]["prompt_tokens"], r["usage"]["completion_tokens"])
)
def ask(prompt, model="gpt-4o"):
    return client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}]
    )

ask("Explain LLM observability like I'm 5")
print(prof.report_summary())

## EXAMPLES
All runnable examples are inside the examples/ directory:

##Core Examples

example_basic_profiler.py – minimal fake call + cost

example_multiple_calls.py – tags and multiple calls

example_jsonl_logging.py – JSONL logs + reading back

example_model_price_override.py – override pricing table

## Integrations

openai_integration.py – real OpenAI client usage

langchain_integration.py – decorator wrapper over LangChain

fastapi_server.py – API endpoint that tracks cost per request

batch_job.py – batch summarization worker example

## Run any example with:

python examples/example_basic_profiler.py

## Development

Clone the repo and use a virtualenv:

python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
pytest -q

## How the decorator works
@profile_llm_call(
    prof,
    model_getter=lambda args, kwargs: kwargs.get("model"),
    token_getter=lambda resp: (
        resp["usage"]["prompt_tokens"],
        resp["usage"]["completion_tokens"]
    )
)
def llm_call(...):
    ...



##The decorator automatically captures:

# model name

# prompt & completion tokens

# execution time

# estimated cost

# any custom tags you pass

# and logs it as JSONL.


## Configuration / Env

Create a .env (never commit it). Example .env.example:

OPENAI_API_KEY=sk-REPLACE_ME
PRICING_API_KEY=replace-me-if-needed

##Contributing

Contributions welcome — open issues and PRs. Please follow the project's code style and tests.

##License

MIT © Bon