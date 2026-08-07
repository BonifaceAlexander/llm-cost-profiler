"""
Real subprocess-level test for the `llm-cost-profiler dashboard` CLI.

This exists specifically because the AppTest-based tests in
test_dashboard.py run the dashboard script in-process and control it
via environment variables - they never exercise the actual `streamlit
run ... -- --sink ...` subprocess path. A real bug shipped past those
tests: dashboard.py assumed a `--` separator would still be present in
sys.argv inside the streamlit-launched process, but streamlit strips
it before handing off argv, so --sink/--budget were silently ignored
and the dashboard always fell back to defaults - while every AppTest
test still passed, because they never went through sys.argv at all.

These tests launch the real CLI as a subprocess and inspect real
server behavior, closing that gap.
"""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time

import pytest

pytest.importorskip("streamlit")


def _free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _tmp_jsonl(lines):
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as f:
        for line in lines:
            f.write(line + "\n")
    return path


def _wait_for_port(port, timeout=15):
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection(("localhost", port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.3)
    return False


def _fetch_rendered_text(port):
    """Uses a real headless browser (playwright) to trigger Streamlit's
    script execution and read the rendered page text - a plain HTTP
    GET does not trigger script execution, since Streamlit runs the
    script over its websocket session protocol, not on the initial
    page load."""
    pw = pytest.importorskip("playwright.sync_api")
    with pw.sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(f"http://localhost:{port}", wait_until="load", timeout=15000)
        page.wait_for_timeout(3000)
        text = page.evaluate("document.body.innerText")
        browser.close()
        return text


@pytest.mark.slow
def test_cli_dashboard_respects_sink_argument_in_real_subprocess():
    """The actual regression: launch `llm-cost-profiler dashboard
    --sink X` as a real subprocess (going through cli.py -> streamlit
    run -> dashboard.py's real argv parsing) and confirm the dashboard
    actually reads from X, not the default llm_costs.jsonl."""
    data_path = _tmp_jsonl([json.dumps({
        "timestamp": 1234567890.0, "model": "gpt-4o", "prompt_tokens": 10,
        "completion_tokens": 5, "total_tokens": 15, "latency_s": 0.1,
        "cost_usd": 0.0123, "tags": {}, "step": "test_step",
    })])
    port = _free_port()

    proc = subprocess.Popen(
        ["llm-cost-profiler", "dashboard", "--sink", data_path,
         "--port", str(port), "--headless"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    try:
        assert _wait_for_port(port), "dashboard server never started"
        text = _fetch_rendered_text(port)
        assert data_path in text, (
            f"Dashboard did not report reading from {data_path!r} - "
            f"it likely fell back to the default sink. Got:\n{text[:300]}"
        )
        assert "0.0123" in text or "$0.0123" in text, (
            "Sample record's cost was not rendered - sink data wasn't loaded"
        )
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        os.remove(data_path)


@pytest.mark.slow
def test_cli_dashboard_respects_port_argument():
    """Confirms --port actually controls which port streamlit binds
    to - this was also broken by the same class of bug (streamlit-level
    flags placed incorrectly relative to `--` would silently not apply)."""
    port = _free_port()
    proc = subprocess.Popen(
        ["llm-cost-profiler", "dashboard", "--port", str(port), "--headless"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    try:
        assert _wait_for_port(port, timeout=15), (
            f"Server did not come up on the requested port {port}"
        )
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
