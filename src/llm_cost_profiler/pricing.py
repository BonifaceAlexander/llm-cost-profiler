DEFAULT_PRICING = {
    "gpt-4o-mini": {"prompt_per_1k": 0.03, "completion_per_1k": 0.06},
    "gpt-4.1": {"prompt_per_1k": 0.06, "completion_per_1k": 0.12},
    "gpt-3.5-turbo": {"prompt_per_1k": 0.002, "completion_per_1k": 0.002}
}

def estimate_cost(pricing: dict, model: str, prompt_tokens: int, completion_tokens: int) -> float:
    m = pricing.get(model)
    if m:
        per1k_p = m.get("prompt_per_1k", 0.01)
        per1k_c = m.get("completion_per_1k", 0.02)
    else:
        per1k_p = 0.01
        per1k_c = 0.02
    return (prompt_tokens / 1000.0) * per1k_p + (completion_tokens / 1000.0) * per1k_c
