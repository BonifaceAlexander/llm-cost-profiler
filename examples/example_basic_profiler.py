# examples/example_basic_profiler.py
from llm_cost_profiler import CostProfiler, profile_llm_call
import time

prof = CostProfiler("examples_basic_costs.jsonl")

def model_getter(args, kwargs):
    return kwargs.get("model", "gpt-3.5-turbo")

def token_getter(response):
    # Simulated response shape used for examples
    usage = response.get("usage", {})
    return (usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))

@profile_llm_call(prof, model_getter=model_getter, token_getter=token_getter)
def fake_llm(prompt, model="gpt-3.5-turbo"):
    # Simulate latency and usage returned by a real LLM client
    time.sleep(0.1)
    return {"id":"fake","usage":{"prompt_tokens":10,"completion_tokens":20},"text":"Simulated response"}

if __name__ == "__main__":
    fake_llm("Explain observability in 2 sentences.")
    print(prof.report_summary())
