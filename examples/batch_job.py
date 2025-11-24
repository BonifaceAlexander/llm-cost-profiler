# examples/batch_job.py
# Simulates bulk summarization and logs cost per document
from llm_cost_profiler import CostProfiler, profile_llm_call
import time

prof = CostProfiler("examples_batch_costs.jsonl")

def model_getter(a,k): return "gpt-3.5-turbo"
def token_getter(response): return (response["usage"].get("prompt_tokens",0), response["usage"].get("completion_tokens",0))

@profile_llm_call(prof, model_getter=model_getter, token_getter=token_getter)
def fake_summary(doc):
    time.sleep(0.05)
    words = len(doc.split())
    return {"usage":{"prompt_tokens": max(5, words//2), "completion_tokens": 10}, "text":"summary"}

if __name__ == "__main__":
    docs = ["Short doc."]*10 + ["Longer document content " * 20]*3
    for d in docs:
        fake_summary(d)
    print(prof.report_summary())
