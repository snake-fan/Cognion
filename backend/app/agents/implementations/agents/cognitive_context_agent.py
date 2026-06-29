from __future__ import annotations

import json
from typing import Any

from ...core.base import BaseAgent
from ...parsers import parse_cognitive_context_brief
from ...schemas import CognitiveContextBrief, ParseResult
from ...state import ConversationAgentState, build_messages
from ..templates.cognitive_context import build_cognitive_context_system_template, build_cognitive_context_user_template


def _truncate(value: object, *, max_chars: int = 360) -> str:
    text = str(value or "").strip()
    if len(text) <= max_chars:
        return text
    return f"{text[: max_chars - 3].rstrip()}..."


def _candidate_to_prompt_item(candidate: dict[str, Any]) -> dict[str, Any]:
    item: dict[str, Any] = {
        "candidate_id": candidate.get("candidate_id"),
        "kind": candidate.get("kind"),
        "source_scope": candidate.get("source_scope"),
        "score": candidate.get("score"),
    }
    for key in (
        "title",
        "term",
        "topic_key",
        "summary",
        "retrieval_description",
        "core_claim",
        "content_excerpt",
    ):
        value = _truncate(candidate.get(key))
        if value:
            item[key] = value

    cognitive_state = candidate.get("cognitive_state") if isinstance(candidate.get("cognitive_state"), dict) else {}
    mental_model = _truncate(cognitive_state.get("mental_model"))
    if mental_model:
        item["cognitive_state"] = {
            "state": cognitive_state.get("state"),
            "confidence": cognitive_state.get("confidence"),
            "mental_model": mental_model,
        }

    follow_up_questions = candidate.get("follow_up_questions")
    if isinstance(follow_up_questions, list):
        item["follow_up_questions"] = [_truncate(question, max_chars=140) for question in follow_up_questions[:3]]

    linked_notes = candidate.get("linked_notes")
    if isinstance(linked_notes, list):
        item["linked_notes"] = [
            {
                "note_id": note.get("note_id"),
                "title": _truncate(note.get("title"), max_chars=120),
                "summary": _truncate(note.get("summary"), max_chars=220),
                "cognitive_state": note.get("cognitive_state") if isinstance(note.get("cognitive_state"), dict) else {},
            }
            for note in linked_notes[:3]
            if isinstance(note, dict)
        ]

    return item


def _build_candidates_block(candidates: list[dict[str, Any]]) -> str:
    if not candidates:
        return ""
    prompt_candidates = [_candidate_to_prompt_item(candidate) for candidate in candidates[:18]]
    return json.dumps(prompt_candidates, ensure_ascii=False, indent=2)


class CognitiveContextAgent(BaseAgent):
    name = "cognitive_context_agent"

    def __init__(self, *args, **kwargs) -> None:
        kwargs.setdefault("temperature", 0.1)
        kwargs.setdefault("timeout_seconds", 45.0)
        kwargs.setdefault("response_format", {"type": "json_object"})
        super().__init__(*args, **kwargs)

    def build_messages(self, state: ConversationAgentState):
        candidates = state.retrieval_context.get("cognitive_context_candidates")
        prompt = build_cognitive_context_user_template(
            question=state.user_input,
            quote=str(state.retrieval_context.get("quote") or ""),
            pdf_filename=str(state.retrieval_context.get("pdf_filename") or ""),
            candidates_block=_build_candidates_block(candidates if isinstance(candidates, list) else []),
        )
        return build_messages(build_cognitive_context_system_template(), prompt)

    def parse_response(self, raw_text: str) -> ParseResult:
        return parse_cognitive_context_brief(raw_text)

    def apply_result(self, state: ConversationAgentState, parsed: ParseResult) -> None:
        brief = parsed.data if isinstance(parsed.data, CognitiveContextBrief) else CognitiveContextBrief()
        state.retrieval_context["cognitive_context_brief"] = brief.model_dump(mode="json")
        if not parsed.ok and parsed.error:
            state.add_error(self.name, parsed.error.message)
