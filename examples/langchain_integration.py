# examples/langchain_integration.py
# Demonstrates decorator approach with LangChain
#
# Note: ChatOpenAI now lives in the separate `langchain-openai` package
# (pip install langchain-openai) - it moved out of `langchain.chat_models`
# in recent LangChain versions.
from llm_cost_profiler import CostProfiler, profile_llm_call
from langchain_openai import ChatOpenAI

prof = CostProfiler("examples_langchain_costs.jsonl")

def model_getter(args, kwargs):
    return kwargs.get("model") or "gpt-4o"

def token_getter(response):
    # LangChain usage reporting varies by provider; this is a best-effort example.
    try:
        # generation_info / usage keys are provider-specific
        info = response.generations[0][0].generation_info
        usage = info.get("token_usage", {})
        return (usage.get("prompt",0), usage.get("completion",0))
    except Exception:
        return (0,0)

@profile_llm_call(prof, model_key_getter=model_getter, token_counts_getter=token_getter)
def chain_call(prompt, model="gpt-4o"):
    llm = ChatOpenAI(model_name=model)
    return llm.generate([{"role":"user","content":prompt}])

if __name__ == "__main__":
    out = chain_call("Explain vector search simply.")
    print("Done — check", prof.report_summary())
