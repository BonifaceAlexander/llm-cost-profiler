# examples/openai_integration.py
# Requires `openai` package (>=1.0) and an OPENAI_API_KEY env var
from llm_cost_profiler import CostProfiler, profile_llm_call
import os
from openai import OpenAI

api_key = os.environ.get("OPENAI_API_KEY")
client = OpenAI(api_key=api_key) if api_key else None

prof = CostProfiler("examples_openai_costs.jsonl")

def model_getter(args, kwargs): return kwargs.get("model","gpt-3.5-turbo")
def token_getter(response):
    usage = response.usage
    return (usage.prompt_tokens, usage.completion_tokens)

@profile_llm_call(prof, model_key_getter=model_getter, token_counts_getter=token_getter)
def call_openai(prompt, model="gpt-3.5-turbo"):
    resp = client.chat.completions.create(model=model, messages=[{"role":"user","content":prompt}])
    return resp

if __name__ == "__main__":
    if client is None:
        print("Set OPENAI_API_KEY to run this example.")
    else:
        r = call_openai("Summarize the benefits of llm-cost-profiler in one sentence.")
        try:
            print(r.choices[0].message.content)
        except Exception:
            print("Response:", r)
        print(prof.report_summary())
