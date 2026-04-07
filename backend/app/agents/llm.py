from __future__ import annotations

from collections.abc import AsyncGenerator

from .orchestrator import build_default_orchestrator

_orchestrator = build_default_orchestrator()


async def extract_paper_metadata(pdf_bytes: bytes, pdf_filename: str | None) -> dict[str, str]:
    return await _orchestrator.extract_metadata(pdf_bytes, pdf_filename)


async def answer_with_context(
    question: str,
    quote: str,
    pdf_bytes: bytes | None,
    pdf_filename: str | None,
    local_pdf_path: str | None = None,
) -> str:
    return await _orchestrator.answer_qa(
        question=question,
        quote=quote,
        pdf_bytes=pdf_bytes,
        pdf_filename=pdf_filename,
        local_pdf_path=local_pdf_path,
    )


async def answer_with_context_stream(
    question: str,
    quote: str,
    pdf_bytes: bytes | None,
    pdf_filename: str | None,
    local_pdf_path: str | None = None,
) -> AsyncGenerator[str, None]:
    async for token in _orchestrator.answer_qa_stream(
        question=question,
        quote=quote,
        pdf_bytes=pdf_bytes,
        pdf_filename=pdf_filename,
        local_pdf_path=local_pdf_path,
    ):
        yield token


async def generate_notes_from_session(
    paper_title: str,
    paper_authors: str,
    paper_topic: str,
    session_messages: list[dict[str, str]],
    existing_topic_keys: list[str],
    max_points: int | None = None,
) -> list[dict[str, object]]:
    return await _orchestrator.generate_session_notes(
        paper_title=paper_title,
        paper_authors=paper_authors,
        paper_topic=paper_topic,
        session_messages=session_messages,
        existing_topic_keys=existing_topic_keys,
        max_points=max_points,
    )
