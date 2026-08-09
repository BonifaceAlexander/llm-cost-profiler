import asyncio
import os
import tempfile

from llm_cost_profiler import CostProfiler
from llm_cost_profiler.langgraph_integration import profile_node


def _tmp_path():
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    os.remove(path)
    return path


def test_async_node_attribution():
    path = _tmp_path()
    prof = CostProfiler(path)

    @profile_node("async_retrieve", profiler=prof)
    async def async_retrieve(state):
        await asyncio.sleep(0.001)
        prof.record_call("gpt-4.1", 200, 100, 0.001)
        return {"docs": "async docs"}

    async def main():
        await async_retrieve({})

    asyncio.run(main())

    report = prof.report_by_step()
    assert "async_retrieve" in report["steps"]
    assert report["steps"]["async_retrieve"]["cost_usd"] > 0
    assert report["steps"]["async_retrieve"]["calls"] == 2  # node-latency + LLM record
    os.remove(path)


def test_async_node_context_resets_after_exception():
    path = _tmp_path()
    prof = CostProfiler(path)

    @profile_node("async_flaky", profiler=prof)
    async def async_flaky(state):
        raise ValueError("boom")

    async def main():
        try:
            await async_flaky({})
        except ValueError:
            pass
        prof.record_call("gpt-4o", 50, 50, 0.001)  # after node exit -> unattributed

    asyncio.run(main())

    report = prof.report_by_step()
    assert "unattributed" in report["steps"]
    assert report["steps"]["unattributed"]["calls"] == 1
    os.remove(path)


def test_sync_and_async_nodes_dont_cross_contaminate_context():
    """Runs a sync node followed by an async node in the same event loop
    context and confirms each gets its own step attribution."""
    path = _tmp_path()
    prof = CostProfiler(path)

    @profile_node("sync_step", profiler=prof)
    def sync_step(state):
        prof.record_call("gpt-4.1", 100, 100, 0.001)
        return state

    @profile_node("async_step", profiler=prof)
    async def async_step(state):
        await asyncio.sleep(0.001)
        prof.record_call("gpt-3.5-turbo", 50, 50, 0.001)
        return state

    async def main():
        sync_step({})
        await async_step({})

    asyncio.run(main())

    report = prof.report_by_step()
    assert "sync_step" in report["steps"]
    assert "async_step" in report["steps"]
    assert report["steps"]["sync_step"]["cost_usd"] > report["steps"]["async_step"]["cost_usd"]
    os.remove(path)
