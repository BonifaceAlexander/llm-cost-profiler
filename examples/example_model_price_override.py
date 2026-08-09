# examples/example_model_price_override.py
"""Shows how to override/extend the built-in pricing table."""
from llm_cost_profiler import CostProfiler

# Pass a custom pricing dict to the constructor. Keys you provide here
# are merged on top of the built-in DEFAULT_PRICING table, so you only
# need to specify models you want to add or override.
custom_pricing = {
    "super-cheap-model": {"prompt_per_1k": 0.00001, "completion_per_1k": 0.00002},
    "gpt-3.5-turbo": {"prompt_per_1k": 0.0001, "completion_per_1k": 0.0001},  # override built-in price
}

prof = CostProfiler("examples_override_costs.jsonl", pricing=custom_pricing)

rec = prof.record_call("super-cheap-model", 100, 50, 0.05, tags={"note": "custom pricing"})
print("Recorded cost (custom model):", rec.cost_usd)

rec2 = prof.record_call("gpt-3.5-turbo", 100, 50, 0.05, tags={"note": "overridden price"})
print("Recorded cost (overridden built-in):", rec2.cost_usd)

print(prof.report_summary())
