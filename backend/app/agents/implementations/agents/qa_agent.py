from __future__ import annotations

from collections.abc import AsyncGenerator

from ...core.base import BaseAgent
from ...parsers import parse_qa
from ...schemas import ModelCallParams, ParseResult
from ...state import ConversationAgentState, build_messages
from ..templates.qa import build_qa_system_template, build_qa_user_template


class QAAgent(BaseAgent):
    name = "qa_agent"

    def build_messages(self, state: ConversationAgentState):
        prompt = build_qa_user_template(
            question=state.user_input,
            quote=str(state.retrieval_context.get("quote") or ""),
            pdf_filename=str(state.retrieval_context.get("pdf_filename") or ""),
            pdf_context=state.pdf_context,
        )
        return build_messages(build_qa_system_template(), prompt)

    def parse_response(self, raw_text: str) -> ParseResult:
        return parse_qa(raw_text)

    def apply_result(self, state: ConversationAgentState, parsed: ParseResult) -> None:
        answer = str(parsed.data or "")
        state.final_result = answer
        if not parsed.ok and parsed.error:
            state.add_error(self.name, parsed.error.message)

    async def stream(self, state: ConversationAgentState) -> AsyncGenerator[str, None]:
        messages = self.build_messages(state)
        async for token in self.adapter.stream(
            trace_id=state.trace_id,
            workflow=state.workflow,
            paper_id=state.paper_id,
            session_id=state.session_id,
            agent_name=f"{self.name}_stream",
            messages=messages,
            params=ModelCallParams(model=self.model, temperature=self.temperature, response_format=self.response_format),
        ):
            yield token
