from __future__ import annotations

from ...core.base import BaseAgent
from ...parsers import parse_structured_notes
from ...schemas import ParseResult
from ...state import NotesAgentState, build_messages
from ..templates.session_notes import build_session_notes_system_template, build_session_notes_user_template


def _build_session_messages_block(messages: list[dict[str, str]]) -> str:
    lines: list[str] = []
    for message in messages:
        role = "用户" if message.get("role") == "user" else "助手"
        quote = (message.get("quote") or "").strip()
        content = (message.get("content") or "").strip()
        if quote:
            lines.append(f"[{role}引用]\n{quote}")
        if content:
            lines.append(f"[{role}]\n{content}")
    return "\n\n".join(lines).strip()


class NotesAgent(BaseAgent):
    name = "note_agent"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._active_max_points: int | None = None

    def build_messages(self, state: NotesAgentState):
        existing_topic_keys = state.retrieval_context.get("existing_topic_keys")
        existing_keys_text = "\n".join(
            f"- {key}" for key in existing_topic_keys if isinstance(key, str) and key.strip()
        ) or "- （无）"

        max_points = state.retrieval_context.get("max_points")
        self._active_max_points = max_points if isinstance(max_points, int) and max_points > 0 else None
        max_points_line = str(max_points) if isinstance(max_points, int) and max_points > 0 else "3"
        messages_block = _build_session_messages_block(state.conversation_history)

        prompt = build_session_notes_user_template(
            paper_title=str(state.retrieval_context.get("paper_title") or ""),
            paper_authors=str(state.retrieval_context.get("paper_authors") or ""),
            paper_topic=str(state.retrieval_context.get("paper_topic") or ""),
            existing_keys_text=existing_keys_text,
            messages_block=messages_block,
            max_points_line=max_points_line,
        )
        return build_messages(build_session_notes_system_template(), prompt)

    def parse_response(self, raw_text: str) -> ParseResult:
        max_points = self._active_max_points
        return parse_structured_notes(raw_text, max_points=max_points)

    def apply_result(self, state: NotesAgentState, parsed: ParseResult) -> None:
        notes = []
        if isinstance(parsed.data, list):
            state.notes = list(parsed.data)
            notes = [note.model_dump(by_alias=True) for note in parsed.data]
        state.set_agent_output(self.name, {"notes": notes, "fallback_used": parsed.fallback_used})
        if not parsed.ok and parsed.error:
            state.add_error(self.name, parsed.error.message)
