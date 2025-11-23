try:
    from langchain.callbacks.base import BaseCallbackHandler
    HAS_LC = True
except:
    HAS_LC = False

class LangChainCallback:
    def __init__(self, profiler):
        if not HAS_LC:
            raise RuntimeError("LangChain not installed")
        self.profiler = profiler

    def on_llm_end(self, response, **kwargs):
        try:
            out = getattr(response, "llm_output", {}) or response.get("llm_output", {})
            usage = out.get("tokens", {}) or out.get("usage", {})
            p = usage.get("prompt_tokens") or usage.get("input_tokens") or 0
            c = usage.get("completion_tokens") or usage.get("output_tokens") or 0
            model = kwargs.get("model_name") or out.get("model") or "unknown"
            self.profiler.record_call(model, p, c, 0.0, {"langchain":True})
        except Exception as e:
            print("[llm-cost-profiler] LangChainCallback failed:", e)
