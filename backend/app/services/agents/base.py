from __future__ import annotations

from abc import ABC, abstractmethod
from time import perf_counter
from typing import Any

from .model_adapter import ModelAdapterError, OpenAIModelAdapter
from .schemas import AgentExecutionLog, ModelCallParams, ParseResult
from .state import AgentState


class BaseAgent(ABC):
    name = "base_agent"

    def __init__(
        self,
        adapter: OpenAIModelAdapter,
        *,
        model: str | None = None,
        temperature: float | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> None:
        self.adapter = adapter
        self.model = model
        self.temperature = temperature
        self.response_format = response_format

    @abstractmethod
    def build_messages(self, state: AgentState):
        pass

    @abstractmethod
    def parse_response(self, raw_text: str) -> ParseResult:
        pass

    @abstractmethod
    def apply_result(self, state: AgentState, parsed: ParseResult) -> None:
        pass

    async def run(self, state: AgentState) -> AgentState:
        started = perf_counter()
        try:
            messages = self.build_messages(state)
            result = await self.adapter.call(
                trace_id=state.trace_id,
                session_id=state.session_id,
                agent_name=self.name,
                messages=messages,
                params=ModelCallParams(
                    model=self.model,
                    temperature=self.temperature,
                    response_format=self.response_format,
                ),
            )
        except ModelAdapterError as exc:
            latency_ms = int((perf_counter() - started) * 1000)
            state.add_error(self.name, exc)
            state.execution_logs.append(
                AgentExecutionLog(
                    trace_id=state.trace_id,
                    session_id=state.session_id,
                    agent_name=self.name,
                    step_name="run",
                    success=False,
                    latency_ms=latency_ms,
                    error=str(exc),
                )
            )
            raise
        except Exception as exc:
            latency_ms = int((perf_counter() - started) * 1000)
            state.add_error(self.name, exc)
            state.execution_logs.append(
                AgentExecutionLog(
                    trace_id=state.trace_id,
                    session_id=state.session_id,
                    agent_name=self.name,
                    step_name="run",
                    success=False,
                    latency_ms=latency_ms,
                    error=str(exc),
                )
            )
            raise

        try:
            parsed = self.parse_response(result.text)
            self.apply_result(state, parsed)
            success = parsed.ok
            error_message = parsed.error.message if parsed.error else None
        except Exception as exc:
            success = False
            error_message = str(exc)
            state.add_error(self.name, exc)

        latency_ms = int((perf_counter() - started) * 1000)
        state.execution_logs.append(
            AgentExecutionLog(
                trace_id=state.trace_id,
                session_id=state.session_id,
                agent_name=self.name,
                step_name="run",
                success=success,
                latency_ms=latency_ms,
                error=error_message,
            )
        )
        return state
