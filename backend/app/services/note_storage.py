import re
import shutil
from pathlib import Path
from uuid import uuid4

from .config import NOTE_STORAGE_DIR


def _safe_segment(name: str) -> str:
    sanitized = re.sub(r"[\\/:*?\"<>|]+", "_", name).strip()
    return sanitized or "untitled"


def persist_note_markdown(
    title: str,
    content: str,
    folder_segments: list[str] | None = None,
) -> str:
    storage_dir = Path(NOTE_STORAGE_DIR)
    if folder_segments:
        for segment in folder_segments:
            storage_dir = storage_dir / _safe_segment(segment)
    storage_dir.mkdir(parents=True, exist_ok=True)

    stem = _safe_segment(title)[:72]
    stored_name = f"{stem}-{uuid4().hex}.md"
    target_path = storage_dir / stored_name
    target_path.write_text(content, encoding="utf-8")
    return str(target_path.resolve())


def overwrite_note_markdown(file_path: str, content: str) -> str:
    target_path = Path(file_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(content, encoding="utf-8")
    return str(target_path.resolve())


def move_note_file_to_segments(existing_file_path: str, folder_segments: list[str] | None = None) -> str:
    source_path = Path(existing_file_path)
    if not source_path.exists():
        return existing_file_path

    target_dir = Path(NOTE_STORAGE_DIR)
    if folder_segments:
        for segment in folder_segments:
            target_dir = target_dir / _safe_segment(segment)

    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / source_path.name
    shutil.move(str(source_path), str(target_path))
    return str(target_path.resolve())


def rename_note_markdown_file(existing_file_path: str, new_title: str) -> str:
    source_path = Path(existing_file_path)
    if not source_path.exists():
        return existing_file_path

    safe_title = _safe_segment(new_title)[:72]
    stem_parts = source_path.stem.split("-")
    stable_tail = stem_parts[-1] if len(stem_parts) >= 2 else uuid4().hex
    next_name = f"{safe_title}-{stable_tail}{source_path.suffix or '.md'}"
    target_path = source_path.with_name(next_name)

    if target_path == source_path:
        return str(source_path.resolve())

    if target_path.exists():
        target_path = source_path.with_name(f"{safe_title}-{uuid4().hex}{source_path.suffix or '.md'}")

    source_path.rename(target_path)
    return str(target_path.resolve())
