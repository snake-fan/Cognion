from __future__ import annotations

import asyncio
import sys
import threading
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.agents.model_adapter import ModelAdapterError, OpenAIModelAdapter
from backend.app.agents.schemas import ModelInvocationResult, ModelMessage


class FakeModelAdapter(OpenAIModelAdapter):
    def __init__(self) -> None:
        super().__init__(api_key="test-key", base_url="http://test.local/v1", default_model="test-model")
        self.call_thread_ids: list[int] = []

    async def call(self, **kwargs) -> ModelInvocationResult:
        self.call_thread_ids.append(threading.get_ident())
        await asyncio.sleep(0.01)
        return ModelInvocationResult(
            text="ok",
            raw_response={"fake": True},
            token_usage=None,
            latency_ms=10,
            model="test-model",
        )


class FailingModelAdapter(FakeModelAdapter):
    async def call(self, **kwargs) -> ModelInvocationResult:
        self.call_thread_ids.append(threading.get_ident())
        await asyncio.sleep(0.01)
        raise ModelAdapterError("fake failure")


def _messages() -> list[ModelMessage]:
    return [ModelMessage(role="user", content="ping")]


def _call_blocking(adapter: OpenAIModelAdapter) -> ModelInvocationResult:
    return adapter.call_blocking(
        trace_id="trace-test",
        workflow="manual-test",
        paper_id="paper-test",
        session_id="session-test",
        agent_name="fake_agent",
        messages=_messages(),
    )


async def _run_inside_event_loop() -> None:
    adapter = FakeModelAdapter()
    caller_thread_id = threading.get_ident()
    result = _call_blocking(adapter)

    assert result.text == "ok"
    assert adapter.call_thread_ids, "adapter.call was not invoked"
    assert adapter.call_thread_ids[0] != caller_thread_id, "call_blocking did not run call in a worker thread"
    print("inside running loop: ok")


async def _run_error_inside_event_loop() -> None:
    adapter = FailingModelAdapter()
    try:
        _call_blocking(adapter)
    except ModelAdapterError as exc:
        assert str(exc) == "fake failure"
        print("inside running loop error propagation: ok")
        return
    raise AssertionError("ModelAdapterError was not propagated")


def _run_outside_event_loop() -> None:
    adapter = FakeModelAdapter()
    caller_thread_id = threading.get_ident()
    result = _call_blocking(adapter)

    assert result.text == "ok"
    assert adapter.call_thread_ids, "adapter.call was not invoked"
    assert adapter.call_thread_ids[0] == caller_thread_id, "outside-loop call should run on the caller thread"
    print("outside running loop: ok")


def main() -> None:
    _run_outside_event_loop()
    asyncio.run(_run_inside_event_loop())
    asyncio.run(_run_error_inside_event_loop())
    print("call_blocking smoke test passed")


if __name__ == "__main__":
    main()
