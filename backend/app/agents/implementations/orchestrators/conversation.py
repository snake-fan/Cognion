from __future__ import annotations

from collections.abc import AsyncGenerator
from uuid import uuid4

from ....services.mineru import extract_pdf_context_for_qa
from ....services.pdf_storage import extract_pdf_text
from ...model_adapter import ModelAdapterError, OpenAIModelAdapter
from ...parsers import parse_metadata
from ...schemas import ModelCallParams
from ...state import ConversationAgentState, build_messages
from ..agents.qa_agent import QAAgent
from ..templates.metadata import build_metadata_system_template, build_metadata_user_template
from ..templates.fallback import build_fallback_message
from .base import BaseOrchestrator


class ConversationOrchestrator(BaseOrchestrator):
    def __init__(self, adapter: OpenAIModelAdapter | None = None) -> None:
        super().__init__(adapter)
        self.register_agent(QAAgent(self.adapter))

    async def extract_metadata(self, pdf_bytes: bytes, pdf_filename: str | None) -> dict[str, str]:
        pdf_context = extract_pdf_text(pdf_bytes, max_chars=14000)
        prompt = build_metadata_user_template(pdf_filename=pdf_filename, pdf_context=pdf_context)
        messages = build_messages(build_metadata_system_template(), prompt)
        trace_id = uuid4().hex

        try:
            result = await self.adapter.call(
                trace_id=trace_id,
                session_id=None,
                agent_name="metadata_agent",
                messages=messages,
                params=ModelCallParams(temperature=0.1),
            )
            parsed = parse_metadata(result.text, pdf_filename=pdf_filename)
            if parsed.ok and parsed.data is not None:
                return parsed.data.model_dump()
        except ModelAdapterError:
            pass

        fallback = parse_metadata("{}", pdf_filename=pdf_filename)
        return fallback.data.model_dump() if fallback.data is not None else {
            "title": "未命名论文",
            "authors": "未知",
            "research_topic": "未标注",
            "journal": "未知",
            "publication_date": "未知",
            "summary": "",
        }

    async def answer_qa(
        self,
        *,
        question: str,
        quote: str,
        pdf_bytes: bytes | None,
        pdf_filename: str | None,
        local_pdf_path: str | None,
        trace_id: str | None = None,
        session_id: str | None = None,
    ) -> str:
        state = ConversationAgentState(
            trace_id=trace_id or uuid4().hex,
            session_id=session_id,
            user_input=question,
            retrieval_context={"quote": quote, "pdf_filename": pdf_filename},
        )
        state.pdf_context = await extract_pdf_context_for_qa(
            pdf_bytes=pdf_bytes,
            pdf_filename=pdf_filename,
            local_pdf_path=local_pdf_path,
        )

        try:
            await self.run_steps(state, ["qa_agent"])
            return str(state.final_result or "模型未返回可解析内容。")
        except ModelAdapterError:
            prompt = self.get_agent("qa_agent").build_messages(state)[1].content
            return build_fallback_message(prompt)

    async def answer_qa_stream(
        self,
        *,
        question: str,
        quote: str,
        pdf_bytes: bytes | None,
        pdf_filename: str | None,
        local_pdf_path: str | None,
        trace_id: str | None = None,
        session_id: str | None = None,
    ) -> AsyncGenerator[str, None]:
        state = ConversationAgentState(
            trace_id=trace_id or uuid4().hex,
            session_id=session_id,
            user_input=question,
            retrieval_context={"quote": quote, "pdf_filename": pdf_filename},
        )
        state.pdf_context = await extract_pdf_context_for_qa(
            pdf_bytes=pdf_bytes,
            pdf_filename=pdf_filename,
            local_pdf_path=local_pdf_path,
        )

        qa_agent = self.get_agent("qa_agent")
        try:
            async for token in qa_agent.stream(state):
                yield token
        except ModelAdapterError:
            prompt = qa_agent.build_messages(state)[1].content
            yield build_fallback_message(prompt)
