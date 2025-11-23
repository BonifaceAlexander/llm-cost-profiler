import json, time, os
from typing import Dict, Optional
try:
    import requests
except Exception:
    requests = None

CACHE_FILE = os.getenv("LLM_PRICING_CACHE", ".llm_pricing_cache.json")
CACHE_TTL = int(os.getenv("LLM_PRICING_TTL_SECONDS", 24*3600))

def load_cache():
    if not os.path.exists(CACHE_FILE):
        return {}
    try:
        with open(CACHE_FILE, "r") as f:
            obj = json.load(f)
        if time.time() - obj.get("_fetched_at", 0) > CACHE_TTL:
            return {}
        return obj.get("pricing", {})
    except:
        return {}

def save_cache(p):
    with open(CACHE_FILE, "w") as f:
        json.dump({"_fetched_at": time.time(), "pricing": p}, f)

def fetch_openai_pricing() -> Optional[Dict]:
    if requests is None: return None
    try:
        r = requests.get("https://openai.com/pricing", timeout=8)
        if r.status_code != 200: return None
        return None
    except:
        return None

def fetch_gemini_pricing() -> Optional[Dict]:
    return None

PROVIDER_FETCHERS = {
    "openai": fetch_openai_pricing,
    "gemini": fetch_gemini_pricing,
}

def get_dynamic_pricing():
    c = load_cache()
    if c: return c
    if requests is None: return {}
    agg = {}
    for fn in PROVIDER_FETCHERS.values():
        try:
            v = fn()
            if v: agg.update(v)
        except:
            pass
    if agg: save_cache(agg)
    return agg
