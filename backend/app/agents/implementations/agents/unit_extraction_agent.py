from __future__ import annotations

import json

from ...core.base import BaseAgent
from ...parsers import parse_extracted_units
from ...schemas import ParseResult
from ...state import NotesAgentState, build_messages
from ..templates.unit_extraction import build_unit_extraction_system_template, build_unit_extraction_user_template


class UnitExtractionAgent(BaseAgent):
    name = "unit_extraction_agent"

    def build_messages(self, state: NotesAgentState):
        note = state.get_intermediate("active_note")
        prompt = build_unit_extraction_user_template(
            json.dumps(note.model_dump(mode="json") if note is not None else {}, ensure_ascii=False, indent=2)
        )
        return build_messages(build_unit_extraction_system_template(), prompt)

    def parse_response(self, raw_text: str) -> ParseResult:
        note = self._current_note
        source_note_id = getattr(note, "note_id", "") or "note"
        return parse_extracted_units(raw_text, source_note_id=source_note_id)

    @property
    def _current_note(self):
        return getattr(self, "__current_note", None)

    @_current_note.setter
    def _current_note(self, value):
        self.__current_note = value

    async def run(self, state: NotesAgentState) -> NotesAgentState:
        self._current_note = state.get_intermediate("active_note")
        return await super().run(state)

    def apply_result(self, state: NotesAgentState, parsed: ParseResult) -> None:
        note = state.get_intermediate("active_note")
        note_id = getattr(note, "note_id", "") or "note"
        units = list(parsed.data) if isinstance(parsed.data, list) else []
        state.add_note_units(note_id, units)
        if not parsed.ok and parsed.error:
            state.add_error(self.name, parsed.error.message)
