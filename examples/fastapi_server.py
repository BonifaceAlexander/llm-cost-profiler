# examples/fastapi_server.py
# Run: uvicorn examples.fastapi_server:app --reload
from fastapi import FastAPI
from pydantic import BaseModel
from llm_cost_profiler import CostProfiler, profile_llm_call
import os
from openai import OpenAI

api_key = os.environ.get("OPENAI_API_KEY")
client = OpenAI(api_key=api_key) if api_key else None

app = FastAPI()
prof = CostProfiler("examples_fastapi_costs.jsonl")

def model_getter(a,k): return k.get("model","gpt-3.5-turbo")
def token_getter(response):
    usage = response.usage
    return (usage.prompt_tokens, usage.completion_tokens)

@profile_llm_call(prof, model_key_getter=model_getter, token_counts_getter=token_getter)
def call_llm(prompt, model="gpt-3.5-turbo"):
    return client.chat.completions.create(model=model, messages=[{"role":"user","content":prompt}])

class Req(BaseModel):
    text: str

@app.post("/summarize")
async def summarize(req: Req):
    if client is None:
        return {"error":"Set OPENAI_API_KEY to run this locally."}
    resp = call_llm(req.text)
    try:
        text = resp.choices[0].message.content
    except Exception:
        text = str(resp)
    return {"summary": text}
