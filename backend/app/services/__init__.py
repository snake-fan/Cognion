from .config import (
    ALIYUN_OSS_BUCKET,
    ALIYUN_OSS_ENABLED,
    ALIYUN_OSS_ENDPOINT,
    MINERU_API_URL,
    MINERU_ENABLED,
)

__all__ = [
    "ALIYUN_OSS_BUCKET",
    "ALIYUN_OSS_ENABLED",
    "ALIYUN_OSS_ENDPOINT",
    "MINERU_API_URL",
    "MINERU_ENABLED",
    "apply_graph_patch",
    "answer_with_context",
    "answer_with_context_stream",
    "extract_paper_metadata",
    "generate_notes_from_session",
    "call_mineru_api_with_pdf_url",
    "upload_pdf_to_aliyun_oss",
    "move_pdf_file_to_segments",
    "persist_uploaded_pdf",
    "move_note_file_to_segments",
    "persist_note_markdown",
    "overwrite_note_markdown",
    "rename_note_markdown_file",
]


def __getattr__(name):
    if name in {
        "answer_with_context",
        "answer_with_context_stream",
        "extract_paper_metadata",
        "generate_notes_from_session",
    }:
        from ..agents import llm

        return getattr(llm, name)
    if name == "apply_graph_patch":
        from .knowledge_graph import apply_graph_patch

        return apply_graph_patch
    if name in {"call_mineru_api_with_pdf_url", "upload_pdf_to_aliyun_oss"}:
        from . import mineru

        return getattr(mineru, name)
    if name in {
        "move_note_file_to_segments",
        "overwrite_note_markdown",
        "persist_note_markdown",
        "rename_note_markdown_file",
    }:
        from . import note_storage

        return getattr(note_storage, name)
    if name in {"move_pdf_file_to_segments", "persist_uploaded_pdf"}:
        from . import pdf_storage

        return getattr(pdf_storage, name)
    raise AttributeError(name)
