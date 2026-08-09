import os
import json
import tempfile

from llm_cost_profiler import CostProfiler
from llm_cost_profiler.langgraph_integration import profile_node


def _make_profiler():
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    os.remove(path)  # CostProfiler creates it
    return CostProfiler(sink_path=path), path


def test_node_with_no_llm_call_still_recorded():
    prof, path = _make_profiler()

    @profile_node("retrieve", profiler=prof)
    def retrieve(state):
        return state

    retrieve({})

    report = prof.report_by_step()
    assert "retrieve" in report["steps"]
    assert report["steps"]["retrieve"]["cost_usd"] == 0.0
    assert report["steps"]["retrieve"]["calls"] == 1
    os.remove(path)


def test_llm_call_inside_node_is_attributed_to_step():
    prof, path = _make_profiler()

    @profile_node("generate", profiler=prof)
    def generate(state):
        prof.record_call("gpt-4.1", 500, 200, 0.01)  # no explicit step arg
        return state

    generate({})

    report = prof.report_by_step()
    assert "generate" in report["steps"]
    # 1 node-latency record + 1 LLM record = 2 calls under this step
    assert report["steps"]["generate"]["calls"] == 2
    assert report["steps"]["generate"]["cost_usd"] > 0
    os.remove(path)


def test_calls_outside_any_node_are_unattributed():
    prof, path = _make_profiler()
    prof.record_call("gpt-4.1", 500, 200, 0.01)

    report = prof.report_by_step()
    assert "unattributed" in report["steps"]
    os.remove(path)


def test_steps_sorted_by_cost_descending():
    prof, path = _make_profiler()

    @profile_node("expensive", profiler=prof)
    def expensive(state):
        prof.record_call("gpt-4.1", 2000, 2000, 0.01)
        return state

    @profile_node("cheap", profiler=prof)
    def cheap(state):
        prof.record_call("gpt-3.5-turbo", 100, 100, 0.01)
        return state

    cheap({})
    expensive({})

    report = prof.report_by_step()
    first_step = next(iter(report["steps"].keys()))
    assert first_step == "expensive"
    os.remove(path)


def test_context_resets_after_node_exits():
    """After a node finishes, calls made outside it must not still be
    tagged with that node's step name - the contextvar must reset even
    if the node raised an exception."""
    prof, path = _make_profiler()

    @profile_node("flaky", profiler=prof)
    def flaky(state):
        raise ValueError("boom")

    try:
        flaky({})
    except ValueError:
        pass

    prof.record_call("gpt-4.1", 100, 100, 0.01)  # after the node, unattributed

    report = prof.report_by_step()
    assert "unattributed" in report["steps"]
    assert report["steps"]["unattributed"]["calls"] == 1
    os.remove(path)
