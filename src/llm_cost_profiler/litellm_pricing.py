"""
Optional pricing backend using litellm's maintained pricing table
(https://github.com/BerriAI/litellm), which covers hundreds of models
across OpenAI, Anthropic, Google, Cohere, Azure, Bedrock, and more -
instead of this library's small hardcoded DEFAULT_PRICING table.

This is opt-in (`pip install llm-cost-profiler[litellm]`) so the core
package stays dependency-light for anyone who doesn't need it.

Important, tested behavior to know before relying on this:

- OpenAI model names work bare: "gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo".
- For other providers, the reliable, recommended pattern is an
  explicit "provider/model" prefix, e.g.
  "anthropic/claude-sonnet-4-5-20250929", "gemini/gemini-1.5-pro".
  A bare (unprefixed) non-OpenAI name will often raise
  litellm.BadRequestError ("LLM Provider NOT provided") - but this is
  inconsistent in litellm itself and model-specific: e.g. bare
  "claude-sonnet-4-5-20250929" resolved correctly in testing, while
  bare "claude-3-5-sonnet-20241022" did not. Don't rely on a bare
  name working just because it worked once - always prefix.
- Even with the correct prefix, some specific dated model snapshots
  may not (yet) be in litellm's pricing table and will raise
  ("This model isn't mapped yet"). litellm's table is actively
  maintained but can lag brand-new model releases.
- All failure modes above are caught here and turned into a clean
  `None` return, so CostProfiler falls back to its builtin pricing
  table automatically - you will not get a crash, but you may
  silently get the built-in table's generic fallback price rather
  than a real litellm-sourced one. If cost accuracy for a specific
  model matters, verify it once with `litellm_available()` +
  `estimate_cost_litellm(...)` directly before relying on it.
"""

from typing import Optional


def _get_litellm():
    try:
        import litellm
        # Silences litellm's stderr "Provider List: ..." dump that
        # otherwise prints even when we cleanly catch the exception -
        # noisy in a fallback path that's meant to be silent.
        litellm.suppress_debug_info = True
        return litellm
    except ImportError:
        return None


def litellm_available() -> bool:
    return _get_litellm() is not None


def estimate_cost_litellm(model: str, prompt_tokens: int, completion_tokens: int) -> Optional[float]:
    """Return total USD cost for this call using litellm's pricing table,
    or None if litellm isn't installed or doesn't recognize the model
    (see module docstring for when that happens) - callers should fall
    back to the builtin pricing table in that case.
    """
    litellm = _get_litellm()
    if litellm is None:
        return None
    try:
        prompt_cost, completion_cost = litellm.cost_per_token(
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
        return float(prompt_cost) + float(completion_cost)
    except Exception:
        return None
