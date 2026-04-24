from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..model_adapter import ModelAdapterError, OpenAIModelAdapter
from ..schemas import ModelCallParams, ParseResult
from ..state import BaseAgentState


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
    def build_messages(self, state: BaseAgentState):
        pass

    @abstractmethod
    def parse_response(self, raw_text: str) -> ParseResult:
        pass

    @abstractmethod
    def apply_result(self, state: BaseAgentState, parsed: ParseResult) -> None:
        pass

    async def run(self, state: BaseAgentState) -> BaseAgentState:
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
            state.add_error(self.name, exc)
            raise
        except Exception as exc:
            state.add_error(self.name, exc)
            raise

        try:
            parsed = self.parse_response(result.text)
            self.apply_result(state, parsed)
        except Exception as exc:
            state.add_error(self.name, exc)
        return state
