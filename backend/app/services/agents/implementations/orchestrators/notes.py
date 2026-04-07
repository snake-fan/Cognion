from __future__ import annotations

from uuid import uuid4

from ...model_adapter import ModelAdapterError, OpenAIModelAdapter
from ...state import AgentState
from ..agents.notes_agent import NotesAgent
from .base import BaseOrchestrator


class NotesOrchestrator(BaseOrchestrator):
    def __init__(self, adapter: OpenAIModelAdapter | None = None) -> None:
        super().__init__(adapter)
        self.register_agent(NotesAgent(self.adapter))

    async def generate_session_notes(
        self,
        *,
        paper_title: str,
        paper_authors: str,
        paper_topic: str,
        session_messages: list[dict[str, str]],
        existing_topic_keys: list[str],
        max_points: int | None = None,
        trace_id: str | None = None,
        session_id: str | None = None,
    ) -> list[dict[str, object]]:
        if not session_messages:
            return []

        state = AgentState(
            trace_id=trace_id or uuid4().hex,
            session_id=session_id,
            conversation_history=session_messages,
            retrieval_context={
                "paper_title": paper_title,
                "paper_authors": paper_authors,
                "paper_topic": paper_topic,
                "existing_topic_keys": existing_topic_keys,
                "max_points": max_points,
            },
        )

        try:
            await self.run_steps(state, ["notes_agent"])
            return list(state.final_result or [])
        except ModelAdapterError:
            return []
