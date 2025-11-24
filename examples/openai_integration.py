# examples/openai_integration.py
# Requires `openai` package and an OPENAI_API_KEY env var
from llm_cost_profiler import CostProfiler, profile_llm_call
import os
import openai

openai.api_key = os.environ.get("OPENAI_API_KEY", "")

prof = CostProfiler("examples_openai_costs.jsonl")

def model_getter(args, kwargs): return kwargs.get("model","gpt-3.5-turbo")
def token_getter(response):
    # OpenAI's Python client returns dict-like responses sometimes; support both dict and object
    if isinstance(response, dict):
        usage = response.get("usage", {})
        return (usage.get("prompt_tokens",0), usage.get("completion_tokens",0))
    else:
        usage = getattr(response, "usage", {})
        return (getattr(usage, "prompt_tokens", 0), getattr(usage, "completion_tokens", 0))

@profile_llm_call(prof, model_getter=model_getter, token_getter=token_getter)
def call_openai(prompt, model="gpt-3.5-turbo"):
    # Using ChatCompletion example (adjust to your client version)
    resp = openai.ChatCompletion.create(model=model, messages=[{"role":"user","content":prompt}])
    return resp

if __name__ == "__main__":
    if not openai.api_key:
        print("Set OPENAI_API_KEY to run this example.")
    else:
        r = call_openai("Summarize the benefits of llm-cost-profiler in one sentence.")
        try:
            print(r.choices[0].message.content)
        except Exception:
            print("Response:", r)
        print(prof.report_summary())
