from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4

from .schemas import AgentExecutionLog, ModelMessage


@dataclass(slots=True)
class AgentState:
    trace_id: str = field(default_factory=lambda: uuid4().hex)
    session_id: str | None = None
    user_input: str = ""
    conversation_history: list[dict[str, str]] = field(default_factory=list)
    pdf_context: str = ""
    retrieval_context: dict[str, Any] = field(default_factory=dict)
    intermediate: dict[str, Any] = field(default_factory=dict)
    agent_outputs: dict[str, Any] = field(default_factory=dict)
    errors: list[dict[str, Any]] = field(default_factory=list)
    final_result: Any = None
    execution_logs: list[AgentExecutionLog] = field(default_factory=list)

    def add_error(self, agent_name: str, error: Exception | str) -> None:
        self.errors.append(
            {
                "timestamp": datetime.utcnow().isoformat(),
                "agent": agent_name,
                "error": str(error),
            }
        )

    def add_intermediate(self, key: str, value: Any) -> None:
        self.intermediate[key] = value

    def get_intermediate(self, key: str, default: Any = None) -> Any:
        return self.intermediate.get(key, default)

    def set_agent_output(self, agent_name: str, value: Any) -> None:
        self.agent_outputs[agent_name] = value

    def get_agent_output(self, agent_name: str, default: Any = None) -> Any:
        return self.agent_outputs.get(agent_name, default)


def build_messages(system_prompt: str, user_prompt: str) -> list[ModelMessage]:
    return [
        ModelMessage(role="system", content=system_prompt),
        ModelMessage(role="user", content=user_prompt),
    ]
