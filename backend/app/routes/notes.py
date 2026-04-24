from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException
from sqlalchemy.orm import Session

from ..db import ChatMessage, ChatSession, KnowledgeUnit, Note, NoteFolder, Paper, get_db
from ..services import (
    apply_graph_patch,
    generate_notes_from_session,
    move_note_file_to_segments,
    overwrite_note_markdown,
    persist_note_markdown,
    rename_note_markdown_file,
)
from .common import (
    build_note_folder_tree,
    collect_descendant_note_folder_ids,
    knowledge_unit_to_dict,
    normalize_topic_key,
    note_folder_segments,
    note_folder_to_dict,
    note_to_dict,
    note_topic_key,
    sync_markdown_title,
)

router = APIRouter()


@router.get("/papers/{paper_id}/sessions/{session_id}/notes")
def list_session_notes(
    paper_id: str,
    session_id: int,
    db: Session = Depends(get_db),
) -> dict[str, list[dict[str, object]]]:
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    chat_session = (
        db.query(ChatSession)
        .filter(ChatSession.id == session_id, ChatSession.paper_id == paper_id)
        .first()
    )
    if not chat_session:
        raise HTTPException(status_code=404, detail="Session not found")

    notes = (
        db.query(Note)
        .filter(Note.paper_id == paper_id, Note.session_id == session_id)
        .order_by(Note.updated_at.desc(), Note.id.desc())
        .all()
    )
    return {"notes": [note_to_dict(note) for note in notes]}


@router.post("/papers/{paper_id}/sessions/{session_id}/notes/generate")
async def generate_notes_for_session(
    paper_id: str,
    session_id: int,
    folder_id: int | None = None,
    max_points: int | None = None,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    chat_session = (
        db.query(ChatSession)
        .filter(ChatSession.id == session_id, ChatSession.paper_id == paper_id)
        .first()
    )
    if not chat_session:
        raise HTTPException(status_code=404, detail="Session not found")

    if folder_id is not None:
        folder = db.query(NoteFolder).filter(NoteFolder.id == folder_id).first()
        if not folder:
            raise HTTPException(status_code=404, detail="Folder not found")

    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.paper_id == paper_id, ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
        .all()
    )
    if not messages:
        raise HTTPException(status_code=400, detail="当前 Session 暂无对话，无法生成笔记")

    existing_session_notes = db.query(Note).filter(Note.paper_id == paper_id).all()
    existing_topic_keys = [
        note_topic_key(note)
        for note in existing_session_notes
        if note_topic_key(note)
    ]
    existing_knowledge_units = [
        knowledge_unit_to_dict(unit)
        for unit in db.query(KnowledgeUnit).order_by(KnowledgeUnit.updated_at.desc(), KnowledgeUnit.id.asc()).all()
    ]

    pipeline_result = await generate_notes_from_session(
        paper_title=paper.title,
        paper_authors=paper.authors,
        paper_topic=paper.research_topic,
        session_messages=[
            {
                "role": message.role,
                "content": message.content,
                "quote": message.quote,
            }
            for message in messages
        ],
        # 针对当前 Paper 范围内的 topic key，包含但不限于当前 Session 相关的笔记
        existing_topic_keys=existing_topic_keys,
        # 针对全局 knowledge unit
        existing_knowledge_units=existing_knowledge_units,
        max_points=max_points,
    )
    generated_notes = pipeline_result.get("notes") if isinstance(pipeline_result.get("notes"), list) else []

    created_notes: list[Note] = []
    skipped_topics: list[dict[str, str]] = []
    all_topic_keys = {key for key in existing_topic_keys if key}
    notes_by_ref: dict[str, Note] = {}

    for item in generated_notes:
        title = str(item.get("title") or "").strip()
        content = str(item.get("content") or "").strip()
        note_id = str(item.get("note_id") or "").strip()
        summary = str(item.get("summary") or "").strip()
        candidate_topic_key = str(item.get("topic_key") or "").strip()
        normalized_topic_key = normalize_topic_key(candidate_topic_key or title)
        cognitive_state = item.get("cognitive_state") if isinstance(item.get("cognitive_state"), dict) else {}
        follow_up_questions = item.get("follow_up_questions") if isinstance(item.get("follow_up_questions"), list) else []
        dedupe_hints = item.get("dedupe_hints") if isinstance(item.get("dedupe_hints"), dict) else {}

        if not title or not content:
            skipped_topics.append(
                {
                    "title": title or "未命名知识点",
                    "topic_key": normalized_topic_key,
                    "reason": "empty_title_or_content",
                }
            )
            continue

        if normalized_topic_key and normalized_topic_key in all_topic_keys:
            skipped_topics.append(
                {
                    "title": title,
                    "topic_key": normalized_topic_key,
                    "reason": "duplicate_topic",
                }
            )
            continue

        try:
            file_path = persist_note_markdown(title, content, note_folder_segments(db, folder_id))
            note = Note(
                note_id=note_id or "",
                title=title,
                topic_key=normalized_topic_key,
                summary=summary,
                content=content,
                cognitive_state=cognitive_state,
                follow_up_questions=follow_up_questions,
                dedupe_hints=dedupe_hints,
                paper_id=paper_id,
                session_id=session_id,
                folder_id=folder_id,
                file_path=file_path,
            )
            db.add(note)
            db.flush()
            created_notes.append(note)
            notes_by_ref[note.note_id] = note
            if normalized_topic_key:
                all_topic_keys.add(normalized_topic_key)
        except Exception:
            skipped_topics.append(
                {
                    "title": title,
                    "topic_key": normalized_topic_key,
                    "reason": "persist_failed",
                }
            )

    graph_patch = pipeline_result.get("graph_patch") if isinstance(pipeline_result.get("graph_patch"), dict) else {}
    if notes_by_ref:
        apply_graph_patch(
            db,
            graph_patch=graph_patch,
            notes_by_ref=notes_by_ref,
        )

    db.query(ChatSession).filter(ChatSession.id == session_id).update({"updated_at": datetime.utcnow()})
    db.query(Paper).filter(Paper.id == paper_id).update({"updated_at": datetime.utcnow()})
    db.commit()

    for note in created_notes:
        db.refresh(note)

    return {
        "paper_id": paper_id,
        "session_id": session_id,
        "created_notes": [note_to_dict(note) for note in created_notes],
        "skipped_topics": skipped_topics,
    }


@router.get("/notes/folders/tree")
def list_note_folder_tree(db: Session = Depends(get_db)) -> dict[str, list[dict[str, object]]]:
    folders = db.query(NoteFolder).order_by(NoteFolder.name.asc()).all()
    occupied_rows = db.query(Note.folder_id).filter(Note.folder_id.isnot(None)).distinct().all()
    folder_ids_with_notes = {folder_id for (folder_id,) in occupied_rows if folder_id is not None}
    return {"folders": build_note_folder_tree(folders, folder_ids_with_notes)}


@router.post("/notes/folders")
def create_note_folder(
    name: str = Form(...),
    parent_id: int | None = Form(default=None),
    db: Session = Depends(get_db),
) -> dict[str, dict[str, str | int | None]]:
    folder_name = name.strip()
    if not folder_name:
        raise HTTPException(status_code=400, detail="Folder name is required")

    if parent_id is not None:
        parent = db.query(NoteFolder).filter(NoteFolder.id == parent_id).first()
        if not parent:
            raise HTTPException(status_code=404, detail="Parent folder not found")

    folder = NoteFolder(name=folder_name, parent_id=parent_id)
    db.add(folder)
    db.commit()
    db.refresh(folder)
    return {"folder": note_folder_to_dict(folder)}


@router.patch("/notes/folders/{folder_id}/move")
def move_note_folder(
    folder_id: int,
    target_parent_id: int | None = Form(default=None),
    db: Session = Depends(get_db),
) -> dict[str, dict[str, str | int | None]]:
    folder = db.query(NoteFolder).filter(NoteFolder.id == folder_id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    if target_parent_id == folder_id:
        raise HTTPException(status_code=400, detail="Folder cannot be moved into itself")

    if target_parent_id is not None:
        target_parent = db.query(NoteFolder).filter(NoteFolder.id == target_parent_id).first()
        if not target_parent:
            raise HTTPException(status_code=404, detail="Target parent folder not found")

        descendants = collect_descendant_note_folder_ids(folder_id, db.query(NoteFolder).all())
        if target_parent_id in descendants:
            raise HTTPException(status_code=400, detail="Folder cannot be moved into its descendant")

    folder.parent_id = target_parent_id
    folder.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(folder)
    return {"folder": note_folder_to_dict(folder)}


@router.patch("/notes/folders/{folder_id}/rename")
def rename_note_folder(
    folder_id: int,
    name: str = Form(...),
    db: Session = Depends(get_db),
) -> dict[str, dict[str, str | int | None]]:
    folder = db.query(NoteFolder).filter(NoteFolder.id == folder_id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    next_name = name.strip()
    if not next_name:
        raise HTTPException(status_code=400, detail="Folder name is required")

    folder.name = next_name
    folder.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(folder)
    return {"folder": note_folder_to_dict(folder)}


@router.delete("/notes/folders/{folder_id}")
def delete_note_folder(folder_id: int, db: Session = Depends(get_db)) -> dict[str, int]:
    folder = db.query(NoteFolder).filter(NoteFolder.id == folder_id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    all_folders = db.query(NoteFolder).all()
    delete_folder_ids = collect_descendant_note_folder_ids(folder_id, all_folders)

    notes = db.query(Note).filter(Note.folder_id.in_(delete_folder_ids)).all()
    delete_note_ids = [note.id for note in notes]
    for note in notes:
        target_path = Path(note.file_path)
        if target_path.exists():
            target_path.unlink(missing_ok=True)

    if delete_note_ids:
        db.query(Note).filter(Note.id.in_(delete_note_ids)).delete(synchronize_session=False)

    db.query(NoteFolder).filter(NoteFolder.id.in_(delete_folder_ids)).delete(synchronize_session=False)
    db.commit()

    return {"deleted_folders": len(delete_folder_ids), "deleted_notes": len(delete_note_ids)}


@router.get("/notes")
def list_notes(
    folder_id: int | None = None,
    db: Session = Depends(get_db),
) -> dict[str, list[dict[str, object]]]:
    query = db.query(Note)
    if folder_id is not None:
        query = query.filter(Note.folder_id == folder_id)

    notes = query.order_by(Note.updated_at.desc(), Note.id.desc()).all()
    return {"notes": [note_to_dict(note) for note in notes]}


@router.post("/notes")
def create_note(
    title: str = Form(...),
    content: str = Form(default=""),
    folder_id: int | None = Form(default=None),
    paper_id: str | None = Form(default=None),
    session_id: int | None = Form(default=None),
    db: Session = Depends(get_db),
) -> dict[str, dict[str, object]]:
    note_title = title.strip()
    if not note_title:
        raise HTTPException(status_code=400, detail="Note title is required")

    if folder_id is not None:
        folder = db.query(NoteFolder).filter(NoteFolder.id == folder_id).first()
        if not folder:
            raise HTTPException(status_code=404, detail="Folder not found")

    paper = None
    if paper_id is not None:
        paper = db.query(Paper).filter(Paper.id == paper_id).first()
        if not paper:
            raise HTTPException(status_code=404, detail="Paper not found")

    if session_id is not None:
        session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        if paper is not None and session.paper_id != paper.id:
            raise HTTPException(status_code=400, detail="Session does not belong to paper")
        if paper is None:
            paper_id = session.paper_id

    file_path = persist_note_markdown(note_title, content, note_folder_segments(db, folder_id))

    note = Note(
        note_id="",
        title=note_title,
        topic_key=normalize_topic_key(note_title),
        summary="",
        content=content,
        cognitive_state={},
        follow_up_questions=[],
        dedupe_hints={},
        paper_id=paper_id,
        session_id=session_id,
        folder_id=folder_id,
        file_path=file_path,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return {"note": note_to_dict(note)}


@router.get("/notes/{note_id}")
def get_note(note_id: int, db: Session = Depends(get_db)) -> dict[str, dict[str, object]]:
    note = db.query(Note).filter(Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return {"note": note_to_dict(note)}


@router.patch("/notes/{note_id}")
def update_note(
    note_id: int,
    title: str | None = Form(default=None),
    content: str | None = Form(default=None),
    paper_id: str | None = Form(default=None),
    session_id: int | None = Form(default=None),
    db: Session = Depends(get_db),
) -> dict[str, dict[str, object]]:
    note = db.query(Note).filter(Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    previous_title = note.title
    title_changed = False
    if title is not None:
        next_title = title.strip()
        if not next_title:
            raise HTTPException(status_code=400, detail="Note title is required")
        title_changed = next_title != note.title
        note.title = next_title

    if paper_id is not None:
        if paper_id == "0":
            note.paper_id = None
        else:
            paper = db.query(Paper).filter(Paper.id == paper_id).first()
            if not paper:
                raise HTTPException(status_code=404, detail="Paper not found")
            note.paper_id = paper_id

    if session_id is not None:
        if session_id == 0:
            note.session_id = None
        else:
            session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")
            if note.paper_id is not None and session.paper_id != note.paper_id:
                raise HTTPException(status_code=400, detail="Session does not belong to paper")
            if note.paper_id is None:
                note.paper_id = session.paper_id
            note.session_id = session_id

    if content is not None:
        note.content = content

    if title_changed:
        previous_topic_key = normalize_topic_key(note.topic_key or previous_title)
        if not note.topic_key or note.topic_key == previous_topic_key:
            note.topic_key = normalize_topic_key(note.title)
        if content is None:
            note.content = sync_markdown_title(note.content, note.title)

    if title_changed:
        note.file_path = rename_note_markdown_file(note.file_path, note.title)

    note.updated_at = datetime.utcnow()
    overwrite_note_markdown(note.file_path, note.content)
    db.commit()
    db.refresh(note)
    return {"note": note_to_dict(note)}


@router.patch("/notes/{note_id}/move")
def move_note(
    note_id: int,
    target_folder_id: int | None = Form(default=None),
    db: Session = Depends(get_db),
) -> dict[str, dict[str, object]]:
    note = db.query(Note).filter(Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    if target_folder_id is not None:
        target_folder = db.query(NoteFolder).filter(NoteFolder.id == target_folder_id).first()
        if not target_folder:
            raise HTTPException(status_code=404, detail="Target folder not found")

    note.folder_id = target_folder_id
    note.file_path = move_note_file_to_segments(note.file_path, note_folder_segments(db, target_folder_id))
    note.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(note)
    return {"note": note_to_dict(note)}


@router.delete("/notes/{note_id}")
def delete_note(note_id: int, db: Session = Depends(get_db)) -> dict[str, int]:
    note = db.query(Note).filter(Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    target_path = Path(note.file_path)
    if target_path.exists():
        target_path.unlink(missing_ok=True)

    db.query(Note).filter(Note.id == note_id).delete(synchronize_session=False)
    db.commit()
    return {"deleted_notes": 1}
