import re
import shutil
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from pypdf import PdfReader

from .config import PDF_STORAGE_DIR


def extract_pdf_text(pdf_bytes: bytes | None, max_chars: int = 12000) -> str:
    if not pdf_bytes:
        return ""

    reader = PdfReader(BytesIO(pdf_bytes))
    pages_text: list[str] = []

    for page in reader.pages:
        text = page.extract_text() or ""
        if text:
            pages_text.append(text.strip())
        if sum(len(chunk) for chunk in pages_text) >= max_chars:
            break

    all_text = "\n\n".join(pages_text)
    return all_text[:max_chars]


def _safe_segment(name: str) -> str:
    sanitized = re.sub(r"[\\/:*?\"<>|]+", "_", name).strip()
    return sanitized or "untitled"


def persist_uploaded_pdf(
    pdf_bytes: bytes,
    original_filename: str | None,
    folder_segments: list[str] | None = None,
) -> str:
    storage_dir = Path(PDF_STORAGE_DIR)
    if folder_segments:
        for segment in folder_segments:
            storage_dir = storage_dir / _safe_segment(segment)
    storage_dir.mkdir(parents=True, exist_ok=True)

    safe_name = Path(original_filename or "paper.pdf").name
    extension = Path(safe_name).suffix.lower() or ".pdf"
    stored_name = f"{uuid4().hex}{extension}"
    target_path = storage_dir / stored_name
    target_path.write_bytes(pdf_bytes)
    return str(target_path.resolve())


def move_pdf_file_to_segments(existing_file_path: str, folder_segments: list[str] | None = None) -> str:
    source_path = Path(existing_file_path)
    if not source_path.exists():
        return existing_file_path

    target_dir = Path(PDF_STORAGE_DIR)
    if folder_segments:
        for segment in folder_segments:
            target_dir = target_dir / _safe_segment(segment)

    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / source_path.name
    shutil.move(str(source_path), str(target_path))
    return str(target_path.resolve())
