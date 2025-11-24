# examples/fastapi_server.py
# Run: uvicorn examples.fastapi_server:app --reload
from fastapi import FastAPI
from pydantic import BaseModel
from llm_cost_profiler import CostProfiler, profile_llm_call
import os, openai

openai.api_key = os.environ.get("OPENAI_API_KEY", "")
client = openai

app = FastAPI()
prof = CostProfiler("examples_fastapi_costs.jsonl")

def model_getter(a,k): return k.get("model","gpt-3.5-turbo")
def token_getter(response):
    if isinstance(response, dict):
        usage = response.get("usage", {})
        return (usage.get("prompt_tokens",0), usage.get("completion_tokens",0))
    else:
        usage = getattr(response, "usage", {})
        return (getattr(usage, "prompt_tokens", 0), getattr(usage, "completion_tokens", 0))

@profile_llm_call(prof, model_getter=model_getter, token_getter=token_getter)
def call_llm(prompt, model="gpt-3.5-turbo"):
    return client.ChatCompletion.create(model=model, messages=[{"role":"user","content":prompt}])

class Req(BaseModel):
    text: str

@app.post("/summarize")
async def summarize(req: Req):
    if not openai.api_key:
        return {"error":"Set OPENAI_API_KEY to run this locally."}
    resp = call_llm(req.text)
    try:
        text = resp.choices[0].message.content
    except Exception:
        text = str(resp)
    return {"summary": text}
