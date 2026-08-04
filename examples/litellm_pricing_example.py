"""
Uses litellm's maintained pricing table instead of the small builtin
one - covers hundreds of models across OpenAI, Anthropic, Google, and
more, with automatic fallback to the builtin table for any model
litellm doesn't recognize.

Run with:
    pip install llm-cost-profiler[litellm]
    python examples/litellm_pricing_example.py
"""
import os

from llm_cost_profiler import CostProfiler

SINK = "litellm_pricing_costs.jsonl"
if os.path.exists(SINK):
    os.remove(SINK)

prof = CostProfiler(SINK, pricing_source="litellm")

# OpenAI models work with bare names.
rec = prof.record_call("gpt-4o", 1000, 500, latency=0.02)
print(f"gpt-4o: ${rec.cost_usd}")

# Non-OpenAI models: use the explicit 'provider/model' form - this is
# the reliable pattern. Bare non-OpenAI names sometimes work and
# sometimes don't, inconsistently, depending on litellm's internal
# table - don't rely on that, always prefix.
rec = prof.record_call("anthropic/claude-sonnet-4-5-20250929", 1000, 500, latency=0.02)
print(f"anthropic/claude-sonnet-4-5-20250929: ${rec.cost_usd}")

# An unrecognized/very new model falls back to the builtin table's
# generic pricing automatically - no crash, no $0 cost.
rec = prof.record_call("some-brand-new-model-not-yet-in-litellm", 1000, 500, latency=0.02)
print(f"unmapped model (fell back to builtin pricing): ${rec.cost_usd}")

print()
print(prof.report_summary())

os.remove(SINK)
