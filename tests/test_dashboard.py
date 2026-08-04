"""
Headless tests for the Streamlit dashboard, using streamlit's official
testing API (streamlit.testing.v1.AppTest) - runs the real dashboard
script and inspects its output tree, no browser required.
"""
import json
import os
import tempfile

import pytest

pytest.importorskip("streamlit")
pytest.importorskip("pandas")

from streamlit.testing.v1 import AppTest

DASHBOARD_PATH = os.path.join(
    os.path.dirname(__file__), "..", "src", "llm_cost_profiler", "dashboard.py"
)


def _tmp_jsonl(lines):
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as f:
        for line in lines:
            f.write(line + "\n")
    return path


def _run_dashboard(sink_path, budget=None):
    os.environ["LLM_COST_PROFILER_SINK"] = sink_path
    if budget is not None:
        os.environ["LLM_COST_PROFILER_BUDGET"] = str(budget)
    else:
        os.environ.pop("LLM_COST_PROFILER_BUDGET", None)
    at = AppTest.from_file(DASHBOARD_PATH, default_timeout=10)
    at.run()
    return at


def _record(model="gpt-4o", step=None, cost=0.01, prompt=10, completion=5):
    return json.dumps({
        "timestamp": 1234567890.0, "model": model, "prompt_tokens": prompt,
        "completion_tokens": completion, "total_tokens": prompt + completion,
        "latency_s": 0.1, "cost_usd": cost, "tags": {}, "step": step,
    })


def test_dashboard_with_no_data_file_shows_empty_state():
    at = _run_dashboard("this_file_does_not_exist_at_all.jsonl")
    assert not at.exception
    assert len(at.metric) == 0
    assert any("No records yet" in i.value for i in at.info)


def test_dashboard_renders_metrics_and_sections_with_real_data():
    path = _tmp_jsonl([
        _record(model="gpt-4.1", step="generate_answer", cost=0.05),
        _record(model="gpt-3.5-turbo", step="critique", cost=0.001),
    ])
    at = _run_dashboard(path)
    assert not at.exception
    assert len(at.metric) == 3  # total cost, total calls, total tokens
    subheaders = [s.value for s in at.subheader]
    assert "Cost by step" in subheaders
    assert "Cost by model" in subheaders
    assert "Cumulative cost over time" in subheaders
    os.remove(path)


def test_dashboard_budget_exceeded_shows_error_banner():
    path = _tmp_jsonl([_record(cost=5.00)])
    at = _run_dashboard(path, budget=1.00)
    assert not at.exception
    assert any("Budget exceeded" in e.value for e in at.error)
    os.remove(path)


def test_dashboard_budget_not_exceeded_shows_no_error():
    path = _tmp_jsonl([_record(cost=0.10)])
    at = _run_dashboard(path, budget=100.00)
    assert not at.exception
    assert len(at.error) == 0
    os.remove(path)


def test_dashboard_handles_corrupt_trailing_line_without_crashing():
    """A truncated/corrupt final JSONL line (e.g. process killed
    mid-write) must not crash the whole dashboard - it should be
    skipped with a visible warning, and valid rows still render."""
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as f:
        f.write(_record(cost=0.02) + "\n")
        f.write('{"timestamp": 2.0, "model": "gpt-4o", incomplete garbage')  # no trailing newline

    at = _run_dashboard(path)
    assert not at.exception
    assert len(at.metric) == 3
    assert any("Skipped 1 unparseable line" in w.value for w in at.warning)
    os.remove(path)


def test_dashboard_handles_logs_with_no_step_field_at_all():
    """Pre-0.2.0 log files have no 'step' key in the JSON at all
    (not even null) - confirm the dashboard doesn't KeyError on those."""
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as f:
        old_format = json.dumps({
            "timestamp": 1234567890.0, "model": "gpt-4o", "prompt_tokens": 10,
            "completion_tokens": 5, "total_tokens": 15, "latency_s": 0.1,
            "cost_usd": 0.01, "tags": {},
        })  # no "step" key
        f.write(old_format + "\n")

    at = _run_dashboard(path)
    assert not at.exception
    assert len(at.metric) == 3
    os.remove(path)
