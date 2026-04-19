from __future__ import annotations

from uuid import uuid4

from ...model_adapter import ModelAdapterError, OpenAIModelAdapter
from ...state import NotesAgentState
from ....services.knowledge_graph import (
    filter_existing_knowledge_units_for_note,
)
from ..agents.canonicalization_agent import CanonicalizationAgent
from ..agents.graph_update_agent import GraphUpdateAgent
from ..agents.notes_agent import NotesAgent
from ..agents.relation_agent import RelationAgent
from ..agents.unit_extraction_agent import UnitExtractionAgent
from .base import BaseOrchestrator


class NotesOrchestrator(BaseOrchestrator):
    def __init__(self, adapter: OpenAIModelAdapter | None = None) -> None:
        super().__init__(adapter)
        self.register_agent(NotesAgent(self.adapter))
        self.register_agent(UnitExtractionAgent(self.adapter))
        self.register_agent(CanonicalizationAgent(self.adapter))
        self.register_agent(RelationAgent(self.adapter))
        self.register_agent(GraphUpdateAgent(self.adapter))

    async def generate_session_notes(
        self,
        *,
        paper_title: str,
        paper_authors: str,
        paper_topic: str,
        session_messages: list[dict[str, str]],
        existing_topic_keys: list[str],
        existing_knowledge_units: list[dict[str, object]] | None = None,
        max_points: int | None = None,
        trace_id: str | None = None,
        session_id: str | None = None,
    ) -> dict[str, object]:
        if not session_messages:
            return {
                "notes": [],
                "note_units": {},
                "canonicalization_decisions": {},
                "relation_decisions": {},
                "graph_patch": {},
                "provenance_log": [],
                "trace_id": trace_id or uuid4().hex,
            }

        state = NotesAgentState(
            trace_id=trace_id or uuid4().hex,
            session_id=session_id,
            conversation_history=session_messages,
            retrieval_context={
                "paper_title": paper_title,
                "paper_authors": paper_authors,
                "paper_topic": paper_topic,
                "existing_topic_keys": existing_topic_keys,
                "existing_knowledge_units": existing_knowledge_units or [],
                "max_points": max_points,
            },
        )

        try:
            await self.run_steps(state, ["note_agent"])
            for note in state.notes:
                state.add_intermediate("active_note", note)
                await self.run_steps(state, ["unit_extraction_agent"])
                units = state.note_units.get(note.note_id, [])
                state.add_intermediate(
                    "active_canonical_candidates",
                    self._retrieve_candidates_for_note(
                        units=units,
                        existing_knowledge_units=existing_knowledge_units or [],
                    ),
                )
                await self.run_steps(state, ["canonicalization_agent"])
                state.add_intermediate(
                    "active_relation_candidates",
                    self._retrieve_candidates_for_note(
                        units=units,
                        existing_knowledge_units=existing_knowledge_units or [],
                        limit=12,
                    ),
                )
                await self.run_steps(state, ["relation_agent"])

            await self.run_steps(state, ["graph_update_agent"])
            result = dict(state.final_result or {})
            result["trace_id"] = state.trace_id
            return result
        except ModelAdapterError:
            return {
                "notes": [],
                "note_units": {},
                "canonicalization_decisions": {},
                "relation_decisions": {},
                "graph_patch": {},
                "provenance_log": [],
                "trace_id": state.trace_id,
            }

    def _retrieve_candidates_for_note(
        self,
        *,
        units,
        existing_knowledge_units: list[dict[str, object]],
        limit: int = 8,
    ) -> list[dict[str, object]]:
        if not units or not existing_knowledge_units:
            return []
        return filter_existing_knowledge_units_for_note(
            note_units=units,
            existing_knowledge_units=existing_knowledge_units,
            limit=limit,
        )
