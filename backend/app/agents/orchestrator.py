from __future__ import annotations

from collections.abc import AsyncGenerator

from .model_adapter import OpenAIModelAdapter
from .implementations.orchestrators.conversation import ConversationOrchestrator
from .implementations.orchestrators.notes import NotesOrchestrator


class AgentOrchestrator:
    def __init__(self, adapter: OpenAIModelAdapter | None = None) -> None:
        self.conversation = ConversationOrchestrator(adapter)
        self.notes = NotesOrchestrator(self.conversation.adapter)
        self.adapter = self.conversation.adapter

    async def extract_metadata(self, pdf_bytes: bytes, pdf_filename: str | None) -> dict[str, str]:
        return await self.conversation.extract_metadata(pdf_bytes, pdf_filename)

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
        return await self.conversation.answer_qa(
            question=question,
            quote=quote,
            pdf_bytes=pdf_bytes,
            pdf_filename=pdf_filename,
            local_pdf_path=local_pdf_path,
            trace_id=trace_id,
            paper_id=paper_id,
            session_id=session_id,
            conversation_history=conversation_history,
            cognitive_context_candidates=cognitive_context_candidates,
        )

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
        return await self.conversation.generate_session_name(
            question=question,
            quote=quote,
            paper_title=paper_title,
            paper_topic=paper_topic,
            trace_id=trace_id,
            paper_id=paper_id,
            session_id=session_id,
        )

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
        async for token in self.conversation.answer_qa_stream(
            question=question,
            quote=quote,
            pdf_bytes=pdf_bytes,
            pdf_filename=pdf_filename,
            local_pdf_path=local_pdf_path,
            trace_id=trace_id,
            paper_id=paper_id,
            session_id=session_id,
            conversation_history=conversation_history,
            cognitive_context_candidates=cognitive_context_candidates,
        ):
            yield token

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
        paper_id: str | None = None,
        session_id: str | None = None,
    ) -> dict[str, object]:
        return await self.notes.generate_session_notes(
            paper_title=paper_title,
            paper_authors=paper_authors,
            paper_topic=paper_topic,
            session_messages=session_messages,
            existing_topic_keys=existing_topic_keys,
            existing_knowledge_units=existing_knowledge_units,
            max_points=max_points,
            trace_id=trace_id,
            paper_id=paper_id,
            session_id=session_id,
        )


def build_default_orchestrator() -> AgentOrchestrator:
    return AgentOrchestrator()
