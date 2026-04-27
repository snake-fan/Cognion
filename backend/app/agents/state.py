from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4

from .schemas import ModelMessage
from .schemas import (
    CanonicalDecision,
    GraphPatch,
    RelationDecision,
    StructuredNote,
    ExtractedUnit,
)


@dataclass(slots=True)
class BaseAgentState:
    trace_id: str = field(default_factory=lambda: uuid4().hex)
    workflow: str | None = None
    paper_id: str | None = None
    session_id: str | None = None
    user_input: str = ""
    conversation_history: list[dict[str, str]] = field(default_factory=list)
    pdf_context: str = ""
    retrieval_context: dict[str, Any] = field(default_factory=dict)
    intermediate: dict[str, Any] = field(default_factory=dict)
    errors: list[dict[str, Any]] = field(default_factory=list)
    final_result: Any = None

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


@dataclass(slots=True)
class ConversationAgentState(BaseAgentState):
    """Shared conversation-oriented state for QA and future lightweight multi-agent flows."""


@dataclass(slots=True)
class NotesAgentState(BaseAgentState):
    notes: list[StructuredNote] = field(default_factory=list)
    note_units: dict[str, list[ExtractedUnit]] = field(default_factory=dict)
    canonicalization_decisions: dict[str, list[CanonicalDecision]] = field(default_factory=dict)
    relation_decisions: dict[str, list[RelationDecision]] = field(default_factory=dict)
    graph_patch: GraphPatch = field(default_factory=GraphPatch)

    def add_note_units(self, note_id: str, units: list[ExtractedUnit]) -> None:
        self.note_units[note_id] = units

    def add_canonicalization_decisions(self, note_id: str, decisions: list[CanonicalDecision]) -> None:
        self.canonicalization_decisions[note_id] = decisions

    def add_relation_decisions(self, note_id: str, decisions: list[RelationDecision]) -> None:
        self.relation_decisions[note_id] = decisions


def build_messages(system_prompt: str, user_prompt: str) -> list[ModelMessage]:
    return [
        ModelMessage(role="system", content=system_prompt),
        ModelMessage(role="user", content=user_prompt),
    ]
