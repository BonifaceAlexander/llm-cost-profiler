# examples/example_model_price_override.py
from llm_cost_profiler import CostProfiler

prof = CostProfiler("examples_override_costs.jsonl")

# Example of providing custom price table (if supported by library API)
# If your version does not have set_price_table, you can pass per_token_price to record_call directly
try:
    prices = {"super-cheap-model": 0.00001, "gpt-3.5-turbo": 0.0001}
    prof.set_price_table(prices)
except Exception:
    # fallback: demonstrate record_call
    rec = prof.record_call("super-cheap-model", 100, 50, 0.00001, tags={"note":"override"})
    print("Recorded cost (fallback):", rec.cost_usd)

# direct record_call example if set_price_table not available
rec2 = prof.record_call("gpt-3.5-turbo", 100, 50, 0.0001, tags={"note":"direct"})
print("Recorded cost:", rec2.cost_usd)
print(prof.report_summary())
