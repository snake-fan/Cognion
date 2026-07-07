from __future__ import annotations

from collections.abc import AsyncGenerator
from uuid import uuid4

from ....services.mineru import extract_pdf_context_for_qa
from ....services.pdf_storage import extract_pdf_text
from ...model_adapter import ModelAdapterError, OpenAIModelAdapter
from ...parsers import parse_metadata, parse_session_name
from ...schemas import CognitiveContextBrief, ModelCallParams, model_message_content_to_text
from ...state import ConversationAgentState, build_messages
from ..agents.cognitive_context_agent import CognitiveContextAgent
from ..agents.qa_agent import QAAgent
from ..templates.metadata import build_metadata_system_template, build_metadata_user_template
from ..templates.fallback import build_fallback_message
from ..templates.session_name import build_session_name_system_template, build_session_name_user_template
from .base import BaseOrchestrator


class ConversationOrchestrator(BaseOrchestrator):
    def __init__(self, adapter: OpenAIModelAdapter | None = None) -> None:
        super().__init__(adapter)
        self.register_agent(CognitiveContextAgent(self.adapter))
        self.register_agent(QAAgent(self.adapter))

    async def extract_metadata(self, pdf_bytes: bytes, pdf_filename: str | None) -> dict[str, str]:
        pdf_context = extract_pdf_text(pdf_bytes, max_chars=14000)
        prompt = build_metadata_user_template(pdf_filename=pdf_filename, pdf_context=pdf_context)
        messages = build_messages(build_metadata_system_template(), prompt)
        trace_id = uuid4().hex

        try:
            result = await self.adapter.call(
                trace_id=trace_id,
                workflow="conversation",
                paper_id=None,
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

    async def generate_session_name(
        self,
        *,
        question: str,
        quote: str,
        paper_title: str,
        paper_topic: str,
        trace_id: str | None = None,
        paper_id: str | None = None,
        session_id: str | None = None,
    ) -> str:
        prompt = build_session_name_user_template(
            question=question,
            quote=quote,
            paper_title=paper_title,
            paper_topic=paper_topic,
        )
        messages = build_messages(build_session_name_system_template(), prompt)

        try:
            result = await self.adapter.call(
                trace_id=trace_id or uuid4().hex,
                workflow="conversation",
                paper_id=paper_id,
                session_id=session_id,
                agent_name="session_name_agent",
                messages=messages,
                params=ModelCallParams(
                    temperature=0.1,
                    response_format={"type": "json_object"},
                    timeout_seconds=20.0,
                    max_tokens=80,
                ),
            )
            parsed = parse_session_name(result.text)
            return parsed.data if parsed.ok and isinstance(parsed.data, str) else ""
        except Exception:
            return ""

    async def answer_qa(
        self,
        *,
        question: str,
        quote: str,
        pdf_bytes: bytes | None,
        pdf_filename: str | None,
        local_pdf_path: str | None,
        trace_id: str | None = None,
        paper_id: str | None = None,
        session_id: str | None = None,
        conversation_history: list[dict[str, str]] | None = None,
        cognitive_context_candidates: list[dict[str, object]] | None = None,
    ) -> str:
        state = ConversationAgentState(
            trace_id=trace_id or uuid4().hex,
            workflow="conversation",
            paper_id=paper_id,
            session_id=session_id,
            user_input=question,
            conversation_history=conversation_history or [],
            retrieval_context={
                "quote": quote,
                "pdf_filename": pdf_filename,
                "cognitive_context_candidates": cognitive_context_candidates or [],
            },
        )
        await self._select_cognitive_context(state)
        pdf_context = await extract_pdf_context_for_qa(
            pdf_bytes=pdf_bytes,
            pdf_filename=pdf_filename,
            local_pdf_path=local_pdf_path,
        )
        state.pdf_context = pdf_context.text
        state.pdf_file_url = pdf_context.file_url

        try:
            await self.run_steps(state, ["qa_agent"])
            return str(state.final_result or "模型未返回可解析内容。")
        except ModelAdapterError:
            prompt_message = self.get_agent("qa_agent").build_messages(state)[1]
            prompt = model_message_content_to_text(prompt_message.content)
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
        paper_id: str | None = None,
        session_id: str | None = None,
        conversation_history: list[dict[str, str]] | None = None,
        cognitive_context_candidates: list[dict[str, object]] | None = None,
    ) -> AsyncGenerator[str, None]:
        state = ConversationAgentState(
            trace_id=trace_id or uuid4().hex,
            workflow="conversation",
            paper_id=paper_id,
            session_id=session_id,
            user_input=question,
            conversation_history=conversation_history or [],
            retrieval_context={
                "quote": quote,
                "pdf_filename": pdf_filename,
                "cognitive_context_candidates": cognitive_context_candidates or [],
            },
        )
        await self._select_cognitive_context(state)
        pdf_context = await extract_pdf_context_for_qa(
            pdf_bytes=pdf_bytes,
            pdf_filename=pdf_filename,
            local_pdf_path=local_pdf_path,
        )
        state.pdf_context = pdf_context.text
        state.pdf_file_url = pdf_context.file_url

        qa_agent = self.get_agent("qa_agent")
        try:
            async for token in qa_agent.stream(state):
                yield token
        except ModelAdapterError:
            prompt_message = qa_agent.build_messages(state)[1]
            prompt = model_message_content_to_text(prompt_message.content)
            yield build_fallback_message(prompt)

    async def _select_cognitive_context(self, state: ConversationAgentState) -> None:
        empty_brief = CognitiveContextBrief().model_dump(mode="json")
        candidates = state.retrieval_context.get("cognitive_context_candidates")
        if not isinstance(candidates, list) or not candidates:
            state.retrieval_context["cognitive_context_brief"] = empty_brief
            return

        try:
            await self.get_agent("cognitive_context_agent").run(state)
        except Exception:
            state.retrieval_context["cognitive_context_brief"] = empty_brief
            return

        if not isinstance(state.retrieval_context.get("cognitive_context_brief"), dict):
            state.retrieval_context["cognitive_context_brief"] = empty_brief
