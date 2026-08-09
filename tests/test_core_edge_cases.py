"""
Coverage for core CostProfiler behavior that the pre-existing test suite
didn't actually exercise (test_profiler.py / test_price_fetcher.py were
placeholder `assert True` tests).
"""
import os
import json
import tempfile

from llm_cost_profiler import CostProfiler, profile_llm_call
from llm_cost_profiler.langgraph_integration import profile_node


def _tmp_path():
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    os.remove(path)
    return path


def test_dynamic_pricing_source_does_not_crash():
    path = _tmp_path()
    prof = CostProfiler(path, pricing_source="dynamic")
    rec = prof.record_call("gpt-4.1", 100, 100, 0.01)
    assert rec.cost_usd > 0
    os.remove(path)
    cache = ".llm_pricing_cache.json"
    if os.path.exists(cache):
        os.remove(cache)


def test_custom_pricing_overrides_builtin():
    path = _tmp_path()
    custom = {"gpt-3.5-turbo": {"prompt_per_1k": 999.0, "completion_per_1k": 999.0}}
    prof = CostProfiler(path, pricing=custom)
    rec = prof.record_call("gpt-3.5-turbo", 1000, 1000, 0.01)
    assert rec.cost_usd == 1998.0
    os.remove(path)


def test_unknown_model_uses_fallback_pricing():
    path = _tmp_path()
    prof = CostProfiler(path)
    rec = prof.record_call("not-a-real-model", 1000, 1000, 0.01)
    expected = (1000 / 1000.0) * 0.01 + (1000 / 1000.0) * 0.02
    assert abs(rec.cost_usd - expected) < 1e-9
    os.remove(path)


def test_empty_log_reports_dont_crash():
    path = _tmp_path()
    prof = CostProfiler(path)
    summary = prof.report_summary()
    by_step = prof.report_by_step()
    assert summary["meta"]["total_calls"] == 0
    assert by_step["meta"]["total_calls"] == 0
    assert summary["models"] == {}
    assert by_step["steps"] == {}
    os.remove(path)


def test_none_token_counts_coerced_to_zero():
    path = _tmp_path()
    prof = CostProfiler(path)

    @profile_llm_call(
        prof,
        model_key_getter=lambda a, k: "gpt-4.1",
        token_counts_getter=lambda r: (None, None),
    )
    def flaky_call():
        return {}

    flaky_call()
    summary = prof.report_summary()
    assert summary["meta"]["total_calls"] == 1
    assert summary["models"]["gpt-4.1"]["prompt_tokens"] == 0
    os.remove(path)


def test_report_summary_and_report_by_step_totals_agree():
    """The two report methods group the same underlying log differently
    (by model vs. by step) - their grand totals must always match, or
    one of the aggregations has a bug even if it looks fine in isolation."""
    path = _tmp_path()
    prof = CostProfiler(path)

    @profile_node("step_a", profiler=prof)
    def step_a(state):
        prof.record_call("gpt-4.1", 500, 200, 0.01)
        return state

    @profile_node("step_b", profiler=prof)
    def step_b(state):
        prof.record_call("gpt-3.5-turbo", 300, 100, 0.01)
        return state

    step_a({})
    step_b({})
    prof.record_call("gpt-4o", 100, 100, 0.01)  # outside any node

    total_a = prof.report_summary()["meta"]["total_cost_usd"]
    total_b = prof.report_by_step()["meta"]["total_cost_usd"]
    assert total_a == total_b
    assert prof.report_summary()["meta"]["total_calls"] == 5
    assert prof.report_by_step()["meta"]["total_calls"] == 5
    os.remove(path)


def test_unicode_and_special_chars_in_tags_survive_roundtrip():
    path = _tmp_path()
    prof = CostProfiler(path)
    note = 'café — 日本語 — "quoted"'
    prof.record_call("gpt-4.1", 10, 10, 0.01, tags={"note": note})
    with open(path) as f:
        parsed = json.loads(f.readline())
    assert parsed["tags"]["note"] == note
    os.remove(path)


def test_pre_020_jsonl_logs_are_readable_by_report_by_step():
    """Simulates a real 0.1.x log file (no 'step' key at all) to make
    sure upgrading to 0.2.0 doesn't break existing users' historical logs."""
    path = _tmp_path()
    old_format_line = json.dumps({
        "timestamp": 1234567890.0, "model": "gpt-4o", "prompt_tokens": 100,
        "completion_tokens": 50, "total_tokens": 150, "latency_s": 0.5,
        "cost_usd": 0.01, "tags": {},
    })
    with open(path, "w") as f:
        f.write(old_format_line + "\n")

    prof = CostProfiler(path)
    report = prof.report_by_step()
    assert "unattributed" in report["steps"]
    assert report["steps"]["unattributed"]["cost_usd"] == 0.01
    assert prof.report_summary()["models"]["gpt-4o"]["calls"] == 1
    os.remove(path)
