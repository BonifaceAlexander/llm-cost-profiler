# examples/example_multiple_calls.py
from llm_cost_profiler import CostProfiler, profile_llm_call

prof = CostProfiler("examples_multiple_costs.jsonl")

def model_getter(a,k): return k.get("model","gpt-3.5-turbo")
def token_getter(resp): return (resp["usage"]["prompt_tokens"], resp["usage"]["completion_tokens"])

@profile_llm_call(prof, model_getter=model_getter, token_getter=token_getter)
def fake_llm(prompt, model="gpt-3.5-turbo", tag=None):
    return {"usage":{"prompt_tokens":len(prompt.split()), "completion_tokens":5}}

if __name__ == "__main__":
    fake_llm("Short prompt one", tag="feature-a")
    fake_llm("Another prompt two", tag="feature-b")
    fake_llm("Third prompt", tag="feature-a")
    print(prof.report_summary())
