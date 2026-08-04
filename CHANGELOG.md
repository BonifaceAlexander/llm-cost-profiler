# Changelog

All notable changes to this project are documented here.
This project follows [Semantic Versioning](https://semver.org/).

## [0.2.0] - Unreleased

### Added
- **litellm-backed pricing**: `CostProfiler(pricing_source="litellm")`
  prices calls using litellm's maintained pricing table (hundreds of
  models across OpenAI, Anthropic, Google, Cohere, Azure, Bedrock,
  etc.) instead of the small hardcoded `DEFAULT_PRICING` table.
  Falls back to the builtin table automatically for any model litellm
  doesn't recognize - never crashes, never silently returns $0.
  New optional dependency group: `pip install llm-cost-profiler[litellm]`.
  New module: `llm_cost_profiler.litellm_pricing`.
  New example: `examples/litellm_pricing_example.py`.
  **Note**: OpenAI model names work bare ("gpt-4o"); other providers
  need the explicit "provider/model" form ("anthropic/claude-...") -
  a bare non-OpenAI name is *inconsistently* recognized by litellm
  itself depending on the exact model string, so always prefix.
- **Local Streamlit dashboard**: `llm-cost-profiler dashboard --sink
  agent_costs.jsonl` serves a browsable view of total cost/calls/
  tokens, cost by step, cost by model, cumulative cost over time,
  average latency by step, and a budget-exceeded warning banner
  (`--budget`). Also supports `--port` and `--headless`.
  New optional dependency group: `pip install llm-cost-profiler[dashboard]`.
  New modules: `llm_cost_profiler.dashboard`, `llm_cost_profiler.cli`.
  New console script: `llm-cost-profiler`.
  New `[all]` extra installing every optional dependency group.
- **Per-agent-step cost attribution** (`llm_cost_profiler.langgraph_integration`):
  - `profile_node(step_name, profiler=...)` — wraps a LangGraph node so
    every LLM call made inside it is automatically tagged with that
    node's name, and the node's own wall-clock time is recorded even
    if it makes no LLM call at all.
  - `LangGraphCostCallback` — a LangChain callback that tags records
    with the currently-executing step, for use alongside `profile_node`.
  - `CostProfiler.report_by_step()` — aggregates cost, tokens, and
    latency per step, sorted with the most expensive step first.
  - New optional dependency group: `pip install llm-cost-profiler[langgraph]`.
  - New example: `examples/langgraph_step_attribution.py`.
- `CallRecord` now has an optional `step` field. `record_call()` falls
  back to the active `profile_node` context if `step` isn't passed
  explicitly, so existing `@profile_llm_call`-decorated functions get
  step attribution for free when called from inside a wrapped node —
  no changes needed to functions you've already instrumented.

### Fixed
- **`CostProfiler.__init__` parameter order was wrong.** `pricing` was
  the first positional argument while every example and the README
  called `CostProfiler("some_file.jsonl")` expecting that to be
  `sink_path`. This crashed with `TypeError: 'str' object is not a
  mapping` on the very first line of the Quick Start. `sink_path` is
  now the first positional parameter, matching all real usage. Anyone
  passing custom pricing must now use the `pricing=` keyword
  (nothing in the existing docs/examples did otherwise, since the old
  positional order never worked in practice).
- **`profile_llm_call` kwarg name mismatch.** README and 6 of 8
  example files called the decorator with `model_getter=`/
  `token_getter=`, but the actual parameters are `model_key_getter`/
  `token_counts_getter`. This raised `TypeError` immediately.
  Corrected everywhere.
- `example_model_price_override.py` called a `set_price_table()`
  method that doesn't exist anywhere in the library, silently falling
  into an unrelated fallback path. Rewritten to demonstrate the
  actual supported way to override pricing (`CostProfiler(pricing=...)`).
- `langchain_integration.py` imported `ChatOpenAI` from
  `langchain.chat_models`, which moved to the separate
  `langchain-openai` package in current LangChain versions. Updated
  the import and noted the new dependency in the file.
- README had an unclosed Markdown code fence around the Installation/
  Quick Start section, which broke rendering of everything below it
  on GitHub and PyPI.
- "Configuration / Env" section documented a `PRICING_API_KEY`
  variable that isn't read anywhere in the code, and omitted the two
  variables that actually are (`LLM_PRICING_CACHE`,
  `LLM_PRICING_TTL_SECONDS`). Corrected to match the real code.
- 5 bare `except:` clauses (which also silently swallow
  `KeyboardInterrupt`/`SystemExit`, not just real errors) tightened to
  `except Exception:` in `price_fetcher.py`, `profiler.py`, and
  `wrappers.py`. Behavior for normal error paths is unchanged.
- Dashboard's `load_records()` crashed on a corrupt/truncated final
  JSONL line (a realistic failure mode if a writer process is killed
  mid-write). Now skips unparseable lines with a visible warning
  instead of crashing the whole dashboard.
- Dashboard used the deprecated `use_container_width` Streamlit
  parameter (removed after 2025-12-31 per Streamlit's own deprecation
  notice); switched to `width="stretch"`.
- First draft of the CLI forwarded all `dashboard` subcommand
  arguments after Streamlit's `--` separator, meaning streamlit-level
  flags like `--port`/`--headless` never reached Streamlit itself
  (they'd silently break the page instead, since they'd hit our own
  script's argparse as unrecognized arguments). Rewritten so
  streamlit-level flags are placed before `--` and app-level flags
  (`--sink`, `--budget`) after it; verified against a real subprocess
  launch, not just unit tests.

### Testing
- `test_profiler.py` and `test_price_fetcher.py` were placeholder
  (`assert True`) tests with no real coverage. Added:
  - `tests/test_core_edge_cases.py` — dynamic pricing construction,
    custom pricing overrides, unknown-model fallback pricing, empty
    logs, `None` token counts, cross-report total consistency between
    `report_summary()` and `report_by_step()`, unicode/special chars
    in tags, and confirming pre-0.2.0 JSONL logs (no `step` key) still
    read correctly under the new `report_by_step()`.
  - `tests/test_async_node.py` — `profile_node` on `async def` nodes,
    including exception-safety and sync/async context isolation.
  - `tests/test_step_attribution.py` — the core new feature: node
    attribution, unattributed calls, cost-sorted ordering, and
    contextvar reset on exception.
  - `tests/test_litellm_pricing.py` — real litellm API calls (not
    mocked): known models, unmapped models, provider-prefix behavior,
    end-to-end `CostProfiler` integration and fallback. Skips cleanly
    (not fail) when litellm isn't installed.
  - `tests/test_dashboard.py` — headless dashboard tests via
    Streamlit's official `AppTest` API: empty state, real data
    rendering, budget banner, corrupt-line handling, old-format logs.
  - 30 tests total, up from 2 placeholders.

### Compatibility
- `report_summary()` and the existing `profile_llm_call` /
  `LangChainCallback` behavior are unchanged. The `step` field
  defaults to `None` and existing JSONL logs remain readable.
- The `CostProfiler.__init__` parameter reorder (see Fixed, above) is
  technically a breaking change to the documented signature, but since
  the old order made every documented usage pattern crash, no working
  code relied on the old order. If you were calling
  `CostProfiler(my_pricing_dict)` positionally (undocumented, and
  not demonstrated anywhere), switch to `CostProfiler(pricing=my_pricing_dict)`.

## [0.1.3] - 2025-11-24
- Initial tracked release (token usage, latency, cost tracking,
  JSONL logging, `profile_llm_call` decorator, LangChain callback,
  dynamic pricing support).
