import os
import tempfile
import pytest

from llm_cost_profiler import CostProfiler
from llm_cost_profiler.litellm_pricing import litellm_available, estimate_cost_litellm

litellm_installed = litellm_available()
requires_litellm = pytest.mark.skipif(not litellm_installed, reason="litellm not installed")


def _tmp_path():
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    os.remove(path)
    return path


def test_litellm_unavailable_returns_none_gracefully(monkeypatch):
    """If litellm isn't installed, estimate_cost_litellm must return None
    (not raise), regardless of whether it's actually installed in this
    test environment - simulate the not-installed case directly."""
    import llm_cost_profiler.litellm_pricing as mod
    monkeypatch.setattr(mod, "_get_litellm", lambda: None)
    assert mod.estimate_cost_litellm("gpt-4o", 100, 100) is None
    assert mod.litellm_available() is False


@requires_litellm
def test_litellm_known_openai_model():
    cost = estimate_cost_litellm("gpt-4o", 1000, 500)
    assert cost is not None
    assert cost > 0


@requires_litellm
def test_litellm_unmapped_model_returns_none():
    cost = estimate_cost_litellm("definitely-not-a-real-model-xyz", 1000, 500)
    assert cost is None


@requires_litellm
def test_litellm_provider_prefixed_model_works_reliably():
    """The reliable, recommended pattern for non-OpenAI models is the
    explicit 'provider/model' form. Whether a *bare* (unprefixed) name
    also happens to work is inconsistent and model-specific in litellm
    itself - e.g. at the time this test was written, a bare
    'claude-sonnet-4-5-20250929' resolved fine but a bare
    'claude-3-5-sonnet-20241022' raised BadRequestError. We don't
    assert on that inconsistency (it could change with litellm
    versions); we only assert that the prefixed form - the pattern
    this library's docs recommend - works."""
    prefixed = estimate_cost_litellm("anthropic/claude-sonnet-4-5-20250929", 1000, 500)
    assert prefixed is not None
    assert prefixed > 0


@requires_litellm
def test_costprofiler_with_litellm_pricing_source():
    path = _tmp_path()
    prof = CostProfiler(path, pricing_source="litellm")
    rec = prof.record_call("gpt-4o", 1000, 500, 0.01)
    assert rec.cost_usd > 0
    os.remove(path)


@requires_litellm
def test_costprofiler_litellm_falls_back_to_builtin_for_unmapped_model():
    """An unmapped model under pricing_source='litellm' must not crash
    or silently produce $0 cost - it should fall back to the builtin
    table's generic fallback pricing, same as pricing_source='builtin'
    would for an unknown model."""
    path = _tmp_path()
    prof = CostProfiler(path, pricing_source="litellm")
    rec = prof.record_call("totally-unmapped-model-xyz", 1000, 1000, 0.01)
    expected_fallback = (1000 / 1000.0) * 0.01 + (1000 / 1000.0) * 0.02
    assert abs(rec.cost_usd - expected_fallback) < 1e-9
    os.remove(path)
