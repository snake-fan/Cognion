from __future__ import annotations

import json

from ...core.base import BaseAgent
from ...parsers import parse_relation_decisions
from ...schemas import ParseResult
from ...state import NotesAgentState, build_messages
from ..templates.relation import build_relation_system_template, build_relation_user_template


class RelationAgent(BaseAgent):
    name = "relation_agent"

    def build_messages(self, state: NotesAgentState):
        note = state.get_intermediate("active_note")
        note_id = getattr(note, "note_id", "") or ""
        units = state.note_units.get(note_id, [])
        candidates = state.get_intermediate("active_relation_candidates") or []
        prompt = build_relation_user_template(
            json.dumps(note.model_dump(mode="json") if note is not None else {}, ensure_ascii=False, indent=2),
            json.dumps([unit.model_dump(mode="json") for unit in units], ensure_ascii=False, indent=2),
            json.dumps(candidates, ensure_ascii=False, indent=2),
        )
        return build_messages(build_relation_system_template(), prompt)

    def parse_response(self, raw_text: str) -> ParseResult:
        return parse_relation_decisions(raw_text)

    def apply_result(self, state: NotesAgentState, parsed: ParseResult) -> None:
        note = state.get_intermediate("active_note")
        note_id = getattr(note, "note_id", "") or ""
        relations = list(parsed.data) if isinstance(parsed.data, list) else []
        state.add_relation_decisions(note_id, relations)
        if not parsed.ok and parsed.error:
            state.add_error(self.name, parsed.error.message)
