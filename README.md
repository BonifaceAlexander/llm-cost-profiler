# llm-cost-profiler


[![PyPI version](https://img.shields.io/pypi/v/llm-cost-profiler?label=PyPI)](https://pypi.org/project/llm-cost-profiler/0.1.0/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)


Lightweight LLM cost, token, and latency profiler for any Python AI stack.


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


## Installation


Install from PyPI:


```bash
pip install llm-cost-profiler