#!/usr/bin/env python
"""Remove storage files that are no longer referenced by the database."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import select

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db import Note, Paper, SessionLocal  # noqa: E402
from app.services.config import NOTE_STORAGE_DIR, PDF_STORAGE_DIR  # noqa: E402


def _resolve_existing_or_parent(path: str | Path) -> Path:
    candidate = Path(path).expanduser()
    if candidate.exists():
        return candidate.resolve()

    parent = candidate.parent
    if parent.exists():
        return parent.resolve() / candidate.name
    return candidate.resolve()


def _is_relative_to(path: Path, directory: Path) -> bool:
    try:
        path.relative_to(directory)
        return True
    except ValueError:
        return False


def _iter_files(directory: Path) -> list[Path]:
    if not directory.exists():
        return []
    return sorted(path.resolve() for path in directory.rglob("*") if path.is_file())


def _collect_referenced_paths() -> tuple[set[Path], set[Path]]:
    paper_paths: set[Path] = set()
    note_paths: set[Path] = set()

    with SessionLocal() as db:
        for file_path in db.execute(select(Paper.file_path)).scalars():
            if not file_path:
                continue
            paper_path = _resolve_existing_or_parent(file_path)
            paper_paths.add(paper_path)
            if paper_path.suffix.lower() == ".pdf":
                paper_paths.add(paper_path.with_suffix(".md"))

        for file_path in db.execute(select(Note.file_path)).scalars():
            if not file_path:
                continue
            note_paths.add(_resolve_existing_or_parent(file_path))

    return paper_paths, note_paths


def _orphan_files(storage_dir: Path, referenced_paths: set[Path]) -> list[Path]:
    storage_dir = storage_dir.resolve()
    safe_references = {
        path
        for path in referenced_paths
        if _is_relative_to(path, storage_dir)
    }
    return [
        path
        for path in _iter_files(storage_dir)
        if path not in safe_references
    ]


def _empty_directories_after_cleanup(directory: Path, removed_files: list[Path]) -> list[Path]:
    if not directory.exists():
        return []

    removed_file_set = {path.resolve() for path in removed_files}
    empty_dir_set: set[Path] = set()
    for path in sorted((item for item in directory.rglob("*") if item.is_dir()), reverse=True):
        try:
            has_remaining_child = False
            for child in path.iterdir():
                child_path = child.resolve()
                if child.is_file() and child_path in removed_file_set:
                    continue
                if child.is_dir() and child_path in empty_dir_set:
                    continue
                has_remaining_child = True
                break
            if not has_remaining_child:
                empty_dir_set.add(path.resolve())
        except OSError:
            continue
    return sorted(empty_dir_set, reverse=True)


def _remove_directories(paths: list[Path]) -> None:
    for path in paths:
        try:
            path.rmdir()
        except OSError:
            continue


def _format_path(path: Path) -> str:
    try:
        return str(path.relative_to(BACKEND_DIR))
    except ValueError:
        return str(path)


def sync_storage(*, apply: bool, prune_empty_dirs: bool) -> int:
    paper_storage_dir = Path(PDF_STORAGE_DIR).expanduser().resolve()
    note_storage_dir = Path(NOTE_STORAGE_DIR).expanduser().resolve()
    paper_references, note_references = _collect_referenced_paths()

    cleanup_targets = [
        ("papers", paper_storage_dir, _orphan_files(paper_storage_dir, paper_references)),
        ("notes", note_storage_dir, _orphan_files(note_storage_dir, note_references)),
    ]

    total_files = sum(len(files) for _, _, files in cleanup_targets)
    action = "Deleting" if apply else "Dry run: would delete"

    for label, directory, files in cleanup_targets:
        print(f"{label}: {len(files)} orphan file(s) under {_format_path(directory)}")
        for path in files:
            print(f"  {action} {_format_path(path)}")
            if apply:
                path.unlink(missing_ok=True)

    empty_dirs: list[Path] = []
    if prune_empty_dirs:
        for _, directory, files in cleanup_targets:
            empty_dirs.extend(_empty_directories_after_cleanup(directory, files))
        if apply:
            _remove_directories(empty_dirs)

    if prune_empty_dirs:
        dir_action = "Removing" if apply else "Dry run: would remove"
        print(f"empty directories: {len(empty_dirs)}")
        for path in empty_dirs:
            print(f"  {dir_action} {_format_path(path)}")

    if apply:
        print(f"Deleted {total_files} orphan file(s).")
    else:
        print("No files were deleted. Re-run with --apply to delete the listed files.")

    return total_files


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Synchronize local storage with database file references.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Delete orphan files. Without this flag the script only prints a dry run.",
    )
    parser.add_argument(
        "--keep-empty-dirs",
        action="store_true",
        help="Keep empty folders after deleting orphan files.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    sync_storage(apply=args.apply, prune_empty_dirs=not args.keep_empty_dirs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
