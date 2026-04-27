from __future__ import annotations

import json

from ...core.base import BaseAgent
from ...parsers import parse_canonical_decisions
from ...schemas import CanonicalDecision, CanonicalizationAction, ParseResult
from ...state import NotesAgentState, build_messages
from ..templates.canonicalization import (
    build_canonicalization_system_template,
    build_canonicalization_user_template,
)


class CanonicalizationAgent(BaseAgent):
    name = "canonicalization_agent"

    def __init__(self, *args, **kwargs) -> None:
        kwargs.setdefault("stream_response", True)
        super().__init__(*args, **kwargs)

    def build_messages(self, state: NotesAgentState):
        note = state.get_intermediate("active_note")
        note_id = getattr(note, "note_id", "") or ""
        units = state.note_units.get(note_id, [])
        candidates = state.get_intermediate("active_canonical_candidates") or []
        prompt = build_canonicalization_user_template(
            json.dumps([unit.model_dump(mode="json") for unit in units], ensure_ascii=False, indent=2),
            json.dumps(candidates, ensure_ascii=False, indent=2),
        )
        return build_messages(build_canonicalization_system_template(), prompt)

    def parse_response(self, raw_text: str) -> ParseResult:
        return parse_canonical_decisions(raw_text)

    def apply_result(self, state: NotesAgentState, parsed: ParseResult) -> None:
        note = state.get_intermediate("active_note")
        note_id = getattr(note, "note_id", "") or ""
        units = state.note_units.get(note_id, [])
        decisions = list(parsed.data) if isinstance(parsed.data, list) else []
        existing = {decision.source_unit_id for decision in decisions}
        missing_unit_ids: list[str] = []
        for unit in units:
            if unit.unit_id in existing:
                continue
            missing_unit_ids.append(unit.unit_id)
            decisions.append(
                CanonicalDecision(
                    source_unit_id=unit.unit_id,
                    action=CanonicalizationAction.CREATE_NEW,
                    target_unit_id=None,
                    target_canonical_key=None,
                    confidence=0.3,
                    reason="no_decision_returned",
                )
            )
        if missing_unit_ids:
            state.add_error(
                self.name,
                f"canonicalization decisions missing for units {missing_unit_ids}; applied create_new fallback",
            )
        state.add_canonicalization_decisions(note_id, decisions)
        if not parsed.ok and parsed.error:
            state.add_error(self.name, parsed.error.message)
