# examples/example_jsonl_logging.py
from llm_cost_profiler import CostProfiler
import json

prof = CostProfiler("examples_jsonl_costs.jsonl")

# record_call signature: (model, prompt_tokens, completion_tokens, per_token_price, tags=None)
prof.record_call("gpt-3.5-turbo", 50, 20, 0.0001, tags={"flow":"demo"})
prof.record_call("gpt-4o", 10, 90, 0.0002, tags={"flow":"demo"})

# Read back the file
with open("examples_jsonl_costs.jsonl") as fh:
    for line in fh:
        print(json.dumps(json.loads(line), indent=2))
print("Summary:", prof.report_summary())
