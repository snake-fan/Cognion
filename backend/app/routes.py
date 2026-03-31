from datetime import datetime
import json
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from .database import get_db
from .models import ChatMessage, ChatSession, Folder, Note, NoteFolder, Paper, PaperPlacement
from .services import (
    answer_with_context,
    answer_with_context_stream,
    extract_paper_metadata,
    generate_notes_from_session,
    move_note_file_to_segments,
    move_pdf_file_to_segments,
    overwrite_note_markdown,
    persist_uploaded_pdf,
    persist_note_markdown,
    rename_note_markdown_file,
)

router = APIRouter()


def _paper_to_dict(paper: Paper) -> dict[str, str | int]:
    return {
        "id": paper.id,
        "title": paper.title,
        "authors": paper.authors,
        "research_topic": paper.research_topic,
        "journal": paper.journal,
        "publication_date": paper.publication_date,
        "original_filename": paper.original_filename,
        "file_path": paper.file_path,
        "summary": paper.summary,
        "created_at": paper.created_at.isoformat() if isinstance(paper.created_at, datetime) else "",
        "updated_at": paper.updated_at.isoformat() if isinstance(paper.updated_at, datetime) else "",
    }


def _message_to_dict(message: ChatMessage) -> dict[str, str | int | None]:
    return {
        "id": message.id,
        "paper_id": message.paper_id,
        "session_id": message.session_id,
        "role": message.role,
        "content": message.content,
        "quote": message.quote,
        "created_at": message.created_at.isoformat() if isinstance(message.created_at, datetime) else "",
    }


def _session_to_dict(chat_session: ChatSession) -> dict[str, str | int]:
    return {
        "id": chat_session.id,
        "paper_id": chat_session.paper_id,
        "name": chat_session.name,
        "created_at": chat_session.created_at.isoformat() if isinstance(chat_session.created_at, datetime) else "",
        "updated_at": chat_session.updated_at.isoformat() if isinstance(chat_session.updated_at, datetime) else "",
    }


def _ensure_default_session(db: Session, paper_id: str) -> ChatSession:
    existing = (
        db.query(ChatSession)
        .filter(ChatSession.paper_id == paper_id)
        .order_by(ChatSession.created_at.asc(), ChatSession.id.asc())
        .first()
    )
    if existing:
        return existing

    default_session = ChatSession(paper_id=paper_id, name="Session 1")
    db.add(default_session)
    db.commit()
    db.refresh(default_session)
    return default_session


def _folder_to_dict(folder: Folder) -> dict[str, str | int | None]:
    return {
        "id": folder.id,
        "name": folder.name,
        "parent_id": folder.parent_id,
        "created_at": folder.created_at.isoformat() if isinstance(folder.created_at, datetime) else "",
        "updated_at": folder.updated_at.isoformat() if isinstance(folder.updated_at, datetime) else "",
    }


def _build_folder_tree(
    folders: list[Folder],
    folder_ids_with_papers: set[int] | None = None,
) -> list[dict[str, object]]:
    occupied_folder_ids = folder_ids_with_papers or set()
    node_map: dict[int, dict[str, object]] = {}
    roots: list[dict[str, object]] = []

    for folder in folders:
        node_map[folder.id] = {
            "id": folder.id,
            "name": folder.name,
            "parent_id": folder.parent_id,
            "children": [],
            "has_papers": folder.id in occupied_folder_ids,
        }

    for folder in folders:
        node = node_map[folder.id]
        parent_id = folder.parent_id
        if parent_id and parent_id in node_map:
            parent_node = node_map[parent_id]
            parent_children = parent_node["children"]
            if isinstance(parent_children, list):
                parent_children.append(node)
        else:
            roots.append(node)

    def mark_has_papers(node: dict[str, object]) -> bool:
        has_papers = bool(node.get("has_papers"))
        children = node.get("children")
        if isinstance(children, list):
            for child in children:
                if isinstance(child, dict) and mark_has_papers(child):
                    has_papers = True
        node["has_papers"] = has_papers
        return has_papers

    for root in roots:
        mark_has_papers(root)

    return roots


def _collect_descendant_folder_ids(folder_id: int, folders: list[Folder]) -> set[int]:
    children_map: dict[int | None, list[int]] = {}
    for folder in folders:
        children_map.setdefault(folder.parent_id, []).append(folder.id)

    result: set[int] = set()
    stack = [folder_id]
    while stack:
        current = stack.pop()
        if current in result:
            continue
        result.add(current)
        stack.extend(children_map.get(current, []))

    return result


def _folder_segments(db: Session, folder_id: int | None) -> list[str]:
    if folder_id is None:
        return []

    segments: list[str] = []
    current_id = folder_id
    while current_id is not None:
        folder = db.query(Folder).filter(Folder.id == current_id).first()
        if not folder:
            break
        segments.append(folder.name)
        current_id = folder.parent_id

    segments.reverse()
    return segments


def _note_to_dict(note: Note) -> dict[str, object]:
    structured_data = note.structured_data if isinstance(note.structured_data, dict) else {}
    return {
        "id": note.id,
        "note_id": note.note_id,
        "title": note.title,
        "topic_key": note.topic_key,
        "summary": note.summary,
        "content": note.content,
        "structured_data": structured_data,
        "paper_id": note.paper_id,
        "session_id": note.session_id,
        "folder_id": note.folder_id,
        "file_path": note.file_path,
        "created_at": note.created_at.isoformat() if isinstance(note.created_at, datetime) else "",
        "updated_at": note.updated_at.isoformat() if isinstance(note.updated_at, datetime) else "",
    }


def _note_folder_to_dict(folder: NoteFolder) -> dict[str, str | int | None]:
    return {
        "id": folder.id,
        "name": folder.name,
        "parent_id": folder.parent_id,
        "created_at": folder.created_at.isoformat() if isinstance(folder.created_at, datetime) else "",
        "updated_at": folder.updated_at.isoformat() if isinstance(folder.updated_at, datetime) else "",
    }


def _build_note_folder_tree(folders: list[NoteFolder], folder_ids_with_notes: set[int] | None = None) -> list[dict[str, object]]:
    occupied_folder_ids = folder_ids_with_notes or set()
    node_map: dict[int, dict[str, object]] = {}
    roots: list[dict[str, object]] = []

    for folder in folders:
        node_map[folder.id] = {
            "id": folder.id,
            "name": folder.name,
            "parent_id": folder.parent_id,
            "children": [],
            "has_notes": folder.id in occupied_folder_ids,
        }

    for folder in folders:
        node = node_map[folder.id]
        parent_id = folder.parent_id
        if parent_id and parent_id in node_map:
            parent_node = node_map[parent_id]
            parent_children = parent_node["children"]
            if isinstance(parent_children, list):
                parent_children.append(node)
        else:
            roots.append(node)

    def mark_has_notes(node: dict[str, object]) -> bool:
        has_notes = bool(node.get("has_notes"))
        children = node.get("children")
        if isinstance(children, list):
            for child in children:
                if isinstance(child, dict) and mark_has_notes(child):
                    has_notes = True
        node["has_notes"] = has_notes
        return has_notes

    for root in roots:
        mark_has_notes(root)

    return roots


def _collect_descendant_note_folder_ids(folder_id: int, folders: list[NoteFolder]) -> set[int]:
    children_map: dict[int | None, list[int]] = {}
    for folder in folders:
        children_map.setdefault(folder.parent_id, []).append(folder.id)

    result: set[int] = set()
    stack = [folder_id]
    while stack:
        current = stack.pop()
        if current in result:
            continue
        result.add(current)
        stack.extend(children_map.get(current, []))

    return result


def _note_folder_segments(db: Session, folder_id: int | None) -> list[str]:
    if folder_id is None:
        return []

    segments: list[str] = []
    current_id = folder_id
    while current_id is not None:
        folder = db.query(NoteFolder).filter(NoteFolder.id == current_id).first()
        if not folder:
            break
        segments.append(folder.name)
        current_id = folder.parent_id

    segments.reverse()
    return segments


def _normalize_topic_key(value: str) -> str:
    normalized = " ".join((value or "").strip().lower().split())
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in normalized).strip("-")


def _note_topic_key(note: Note) -> str:
    return _normalize_topic_key(note.topic_key or note.title)


def _sync_markdown_title(content: str, title: str) -> str:
    if not content:
        return content
    lines = content.splitlines()
    if lines and lines[0].startswith("# "):
        lines[0] = f"# {title}"
        return "\n".join(lines)
    return content


@router.post("/ask", response_model=None)
async def ask_about_quote(
    question: str = Form(...),
    quote: str = Form(default=""),
        paper_id: str | None = Form(default=None),
    session_id: int | None = Form(default=None),
    stream: bool = Form(default=False),
    pdf_file: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
):
    paper: Paper | None = None
    chat_session: ChatSession | None = None
    if paper_id is not None:
        paper = db.query(Paper).filter(Paper.id == paper_id).first()
        if not paper:
            raise HTTPException(status_code=404, detail="Paper not found")

        if session_id is not None:
            chat_session = (
                db.query(ChatSession)
                .filter(ChatSession.id == session_id, ChatSession.paper_id == paper_id)
                .first()
            )
            if not chat_session:
                raise HTTPException(status_code=404, detail="Session not found")
        else:
            chat_session = _ensure_default_session(db, paper_id)

    pdf_bytes = await pdf_file.read() if pdf_file else None
    effective_pdf_filename = pdf_file.filename if pdf_file else (paper.original_filename if paper else None)
    effective_pdf_path = paper.file_path if paper else None

    def persist_chat_turn(answer_text: str) -> None:
        if paper_id is None:
            return

        user_message = ChatMessage(
            paper_id=paper_id,
            session_id=chat_session.id if chat_session else None,
            role="user",
            content=question,
            quote=quote or "",
        )
        assistant_message = ChatMessage(
            paper_id=paper_id,
            session_id=chat_session.id if chat_session else None,
            role="assistant",
            content=answer_text,
            quote="",
        )

        db.add(user_message)
        db.add(assistant_message)
        if chat_session is not None:
            db.query(ChatSession).filter(ChatSession.id == chat_session.id).update({"updated_at": datetime.utcnow()})
        db.query(Paper).filter(Paper.id == paper_id).update({"updated_at": datetime.utcnow()})
        db.commit()

    if stream:
        async def event_stream():
            answer_parts: list[str] = []
            try:
                async for delta in answer_with_context_stream(
                    question=question,
                    quote=quote,
                    pdf_bytes=pdf_bytes,
                    pdf_filename=effective_pdf_filename,
                    local_pdf_path=effective_pdf_path,
                ):
                    if not delta:
                        continue

                    answer_parts.append(delta)
                    yield f"event: chunk\ndata: {json.dumps({'delta': delta}, ensure_ascii=False)}\n\n"

                answer_text = "".join(answer_parts)
                persist_chat_turn(answer_text)
                yield f"event: done\ndata: {json.dumps({'answer': answer_text}, ensure_ascii=False)}\n\n"
            except Exception as exc:  # pragma: no cover - runtime path
                yield f"event: error\ndata: {json.dumps({'detail': str(exc)}, ensure_ascii=False)}\n\n"

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    response_text = await answer_with_context(
        question=question,
        quote=quote,
        pdf_bytes=pdf_bytes,
        pdf_filename=effective_pdf_filename,
        local_pdf_path=effective_pdf_path,
    )

    persist_chat_turn(response_text)

    return {"answer": response_text}


@router.post("/papers/upload")
async def upload_paper(
    pdf_file: UploadFile = File(...),
    folder_id: int | None = Form(default=None),
    db: Session = Depends(get_db),
) -> dict[str, dict[str, str | int]]:
    filename = pdf_file.filename or "paper.pdf"
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    pdf_bytes = await pdf_file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="Uploaded PDF is empty")

    if folder_id is not None:
        folder = db.query(Folder).filter(Folder.id == folder_id).first()
        if not folder:
            raise HTTPException(status_code=404, detail="Folder not found")

    file_path = persist_uploaded_pdf(pdf_bytes, filename, folder_segments=_folder_segments(db, folder_id))
    metadata = await extract_paper_metadata(pdf_bytes, filename)

    paper = Paper(
        title=metadata["title"],
        authors=metadata["authors"],
        research_topic=metadata["research_topic"],
        journal=metadata["journal"],
        publication_date=metadata["publication_date"],
        summary=metadata["summary"],
        original_filename=filename,
        file_path=file_path,
    )

    db.add(paper)
    db.commit()
    db.refresh(paper)

    _ensure_default_session(db, paper.id)

    placement = PaperPlacement(paper_id=paper.id, folder_id=folder_id)
    db.add(placement)
    db.commit()

    return {"paper": _paper_to_dict(paper)}


@router.get("/papers")
def list_papers(
    folder_id: int | None = None,
    include_all: bool = False,
    db: Session = Depends(get_db),
) -> dict[str, list[dict[str, str | int]]]:
    query = db.query(Paper).join(PaperPlacement, PaperPlacement.paper_id == Paper.id, isouter=True)
    if include_all:
        pass
    elif folder_id is None:
        query = query.filter(PaperPlacement.folder_id.is_(None))
    else:
        query = query.filter(PaperPlacement.folder_id == folder_id)

    papers = query.order_by(Paper.updated_at.desc()).all()
    return {"papers": [_paper_to_dict(paper) for paper in papers]}


@router.get("/papers/{paper_id}")
def get_paper(paper_id: str, db: Session = Depends(get_db)) -> dict[str, dict[str, str | int]]:
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    return {"paper": _paper_to_dict(paper)}


@router.get("/papers/{paper_id}/file")
def get_paper_file(paper_id: str, db: Session = Depends(get_db)) -> FileResponse:
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    target_path = Path(paper.file_path)
    if not target_path.exists():
        raise HTTPException(status_code=404, detail="Paper file not found")

    return FileResponse(
        path=str(target_path),
        media_type="application/pdf",
        filename=paper.original_filename,
    )


@router.get("/folders/tree")
def list_folder_tree(db: Session = Depends(get_db)) -> dict[str, list[dict[str, object]]]:
    folders = db.query(Folder).order_by(Folder.name.asc()).all()
    occupied_rows = (
        db.query(PaperPlacement.folder_id)
        .filter(PaperPlacement.folder_id.isnot(None))
        .distinct()
        .all()
    )
    folder_ids_with_papers = {folder_id for (folder_id,) in occupied_rows if folder_id is not None}
    return {"folders": _build_folder_tree(folders, folder_ids_with_papers)}


@router.post("/folders")
def create_folder(
    name: str = Form(...),
    parent_id: int | None = Form(default=None),
    db: Session = Depends(get_db),
) -> dict[str, dict[str, str | int | None]]:
    folder_name = name.strip()
    if not folder_name:
        raise HTTPException(status_code=400, detail="Folder name is required")

    if parent_id is not None:
        parent = db.query(Folder).filter(Folder.id == parent_id).first()
        if not parent:
            raise HTTPException(status_code=404, detail="Parent folder not found")

    folder = Folder(name=folder_name, parent_id=parent_id)
    db.add(folder)
    db.commit()
    db.refresh(folder)
    return {"folder": _folder_to_dict(folder)}


@router.patch("/folders/{folder_id}/move")
def move_folder(
    folder_id: int,
    target_parent_id: int | None = Form(default=None),
    db: Session = Depends(get_db),
) -> dict[str, dict[str, str | int | None]]:
    folder = db.query(Folder).filter(Folder.id == folder_id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    if target_parent_id == folder_id:
        raise HTTPException(status_code=400, detail="Folder cannot be moved into itself")

    if target_parent_id is not None:
        target_parent = db.query(Folder).filter(Folder.id == target_parent_id).first()
        if not target_parent:
            raise HTTPException(status_code=404, detail="Target parent folder not found")

        descendants = _collect_descendant_folder_ids(folder_id, db.query(Folder).all())
        if target_parent_id in descendants:
            raise HTTPException(status_code=400, detail="Folder cannot be moved into its descendant")

    folder.parent_id = target_parent_id
    db.commit()
    db.refresh(folder)
    return {"folder": _folder_to_dict(folder)}


@router.patch("/folders/{folder_id}/rename")
def rename_folder(
    folder_id: int,
    name: str = Form(...),
    db: Session = Depends(get_db),
) -> dict[str, dict[str, str | int | None]]:
    folder = db.query(Folder).filter(Folder.id == folder_id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    next_name = name.strip()
    if not next_name:
        raise HTTPException(status_code=400, detail="Folder name is required")

    folder.name = next_name
    folder.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(folder)
    return {"folder": _folder_to_dict(folder)}


@router.patch("/papers/{paper_id}/move")
def move_paper(
    paper_id: str,
    target_folder_id: int | None = Form(default=None),
    db: Session = Depends(get_db),
) -> dict[str, dict[str, str | int]]:
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    if target_folder_id is not None:
        target_folder = db.query(Folder).filter(Folder.id == target_folder_id).first()
        if not target_folder:
            raise HTTPException(status_code=404, detail="Target folder not found")

    placement = db.query(PaperPlacement).filter(PaperPlacement.paper_id == paper_id).first()
    if not placement:
        placement = PaperPlacement(paper_id=paper_id, folder_id=target_folder_id)
        db.add(placement)
    else:
        placement.folder_id = target_folder_id

    paper.file_path = move_pdf_file_to_segments(paper.file_path, _folder_segments(db, target_folder_id))
    paper.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(paper)
    return {"paper": _paper_to_dict(paper)}


@router.delete("/papers/{paper_id}")
def delete_paper(paper_id: str, db: Session = Depends(get_db)) -> dict[str, int]:
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    target_path = Path(paper.file_path)
    if target_path.exists():
        target_path.unlink(missing_ok=True)

    db.query(ChatMessage).filter(ChatMessage.paper_id == paper_id).delete(synchronize_session=False)
    db.query(PaperPlacement).filter(PaperPlacement.paper_id == paper_id).delete(synchronize_session=False)
    db.query(Paper).filter(Paper.id == paper_id).delete(synchronize_session=False)
    db.commit()

    return {"deleted_papers": 1}


@router.delete("/folders/{folder_id}")
def delete_folder(folder_id: int, db: Session = Depends(get_db)) -> dict[str, int]:
    folder = db.query(Folder).filter(Folder.id == folder_id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    all_folders = db.query(Folder).all()
    delete_folder_ids = _collect_descendant_folder_ids(folder_id, all_folders)

    placements = db.query(PaperPlacement).filter(PaperPlacement.folder_id.in_(delete_folder_ids)).all()
    delete_paper_ids = [placement.paper_id for placement in placements]

    if delete_paper_ids:
        papers = db.query(Paper).filter(Paper.id.in_(delete_paper_ids)).all()
        for paper in papers:
            target_path = Path(paper.file_path)
            if target_path.exists():
                target_path.unlink(missing_ok=True)

        db.query(ChatMessage).filter(ChatMessage.paper_id.in_(delete_paper_ids)).delete(synchronize_session=False)
        db.query(PaperPlacement).filter(PaperPlacement.paper_id.in_(delete_paper_ids)).delete(synchronize_session=False)
        db.query(Paper).filter(Paper.id.in_(delete_paper_ids)).delete(synchronize_session=False)

    db.query(Folder).filter(Folder.id.in_(delete_folder_ids)).delete(synchronize_session=False)
    db.commit()

    return {"deleted_folders": len(delete_folder_ids), "deleted_papers": len(delete_paper_ids)}


@router.get("/papers/{paper_id}/messages")
def list_paper_messages(
    paper_id: str,
    session_id: int | None = None,
    db: Session = Depends(get_db),
) -> dict[str, list[dict[str, str | int | None]]]:
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    effective_session = None
    if session_id is not None:
        effective_session = (
            db.query(ChatSession)
            .filter(ChatSession.id == session_id, ChatSession.paper_id == paper_id)
            .first()
        )
        if not effective_session:
            raise HTTPException(status_code=404, detail="Session not found")
    else:
        effective_session = _ensure_default_session(db, paper_id)

    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.paper_id == paper_id, ChatMessage.session_id == effective_session.id)
        .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
        .all()
    )

    return {"messages": [_message_to_dict(message) for message in messages]}


@router.get("/papers/{paper_id}/sessions")
def list_paper_sessions(paper_id: str, db: Session = Depends(get_db)) -> dict[str, list[dict[str, str | int]]]:
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    _ensure_default_session(db, paper_id)

    sessions = (
        db.query(ChatSession)
        .filter(ChatSession.paper_id == paper_id)
        .order_by(ChatSession.updated_at.desc(), ChatSession.id.desc())
        .all()
    )
    return {"sessions": [_session_to_dict(session) for session in sessions]}


@router.post("/papers/{paper_id}/sessions")
def create_paper_session(
    paper_id: str,
    name: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> dict[str, dict[str, str | int]]:
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    existing_count = db.query(ChatSession).filter(ChatSession.paper_id == paper_id).count()
    resolved_name = (name or "").strip() or f"Session {existing_count + 1}"

    new_session = ChatSession(paper_id=paper_id, name=resolved_name)
    db.add(new_session)
    db.query(Paper).filter(Paper.id == paper_id).update({"updated_at": datetime.utcnow()})
    db.commit()
    db.refresh(new_session)
    return {"session": _session_to_dict(new_session)}


@router.patch("/papers/{paper_id}/sessions/{session_id}")
def rename_paper_session(
    paper_id: str,
    session_id: int,
    name: str = Form(...),
    db: Session = Depends(get_db),
) -> dict[str, dict[str, str | int | None]]:
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

    next_name = name.strip()
    if not next_name:
        raise HTTPException(status_code=400, detail="Session name is required")

    chat_session.name = next_name
    chat_session.updated_at = datetime.utcnow()
    db.query(Paper).filter(Paper.id == paper_id).update({"updated_at": datetime.utcnow()})
    db.commit()
    db.refresh(chat_session)
    return {"session": _session_to_dict(chat_session)}


@router.delete("/papers/{paper_id}/sessions/{session_id}")
def delete_paper_session(
    paper_id: str,
    session_id: int,
    db: Session = Depends(get_db),
) -> dict[str, int]:
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

    db.query(ChatMessage).filter(ChatMessage.session_id == session_id).delete(synchronize_session=False)
    db.query(ChatSession).filter(ChatSession.id == session_id).delete(synchronize_session=False)
    db.commit()

    remaining = (
        db.query(ChatSession)
        .filter(ChatSession.paper_id == paper_id)
        .order_by(ChatSession.updated_at.desc(), ChatSession.id.desc())
        .first()
    )
    if not remaining:
        remaining = _ensure_default_session(db, paper_id)

    db.query(Paper).filter(Paper.id == paper_id).update({"updated_at": datetime.utcnow()})
    db.commit()

    return {"deleted_session_id": session_id, "active_session_id": remaining.id}


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
    return {"notes": [_note_to_dict(note) for note in notes]}


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
        _note_topic_key(note)
        for note in existing_session_notes
        if _note_topic_key(note)
    ]

    generated_notes = await generate_notes_from_session(
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
        existing_topic_keys=existing_topic_keys,
        max_points=max_points,
    )

    created_notes: list[Note] = []
    skipped_topics: list[dict[str, str]] = []
    all_topic_keys = {key for key in existing_topic_keys if key}

    for item in generated_notes:
        title = str(item.get("title") or "").strip()
        content = str(item.get("content") or "").strip()
        note_id = str(item.get("note_id") or "").strip()
        summary = str(item.get("summary") or "").strip()
        candidate_topic_key = str(item.get("topic_key") or "").strip()
        normalized_topic_key = _normalize_topic_key(candidate_topic_key or title)
        structured_data = {
            "note_id": note_id,
            "title": title,
            "topic_key": normalized_topic_key,
            "summary": summary,
            "knowledge_unit": item.get("knowledge_unit") if isinstance(item.get("knowledge_unit"), dict) else {},
            "user_model_signal": item.get("user_model_signal")
            if isinstance(item.get("user_model_signal"), dict)
            else {},
            "evidence": item.get("evidence") if isinstance(item.get("evidence"), list) else [],
            "graph_suggestions": item.get("graph_suggestions")
            if isinstance(item.get("graph_suggestions"), dict)
            else {},
            "open_questions": item.get("open_questions") if isinstance(item.get("open_questions"), list) else [],
            "dedupe_hints": item.get("dedupe_hints") if isinstance(item.get("dedupe_hints"), dict) else {},
        }

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
            file_path = persist_note_markdown(title, content, _note_folder_segments(db, folder_id))
            note = Note(
                note_id=note_id or "",
                title=title,
                topic_key=normalized_topic_key,
                summary=summary,
                content=content,
                structured_data=structured_data,
                paper_id=paper_id,
                session_id=session_id,
                folder_id=folder_id,
                file_path=file_path,
            )
            db.add(note)
            created_notes.append(note)
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

    db.query(ChatSession).filter(ChatSession.id == session_id).update({"updated_at": datetime.utcnow()})
    db.query(Paper).filter(Paper.id == paper_id).update({"updated_at": datetime.utcnow()})
    db.commit()

    for note in created_notes:
        db.refresh(note)

    return {
        "paper_id": paper_id,
        "session_id": session_id,
        "created_notes": [_note_to_dict(note) for note in created_notes],
        "skipped_topics": skipped_topics,
    }


@router.get("/notes/folders/tree")
def list_note_folder_tree(db: Session = Depends(get_db)) -> dict[str, list[dict[str, object]]]:
    folders = db.query(NoteFolder).order_by(NoteFolder.name.asc()).all()
    occupied_rows = db.query(Note.folder_id).filter(Note.folder_id.isnot(None)).distinct().all()
    folder_ids_with_notes = {folder_id for (folder_id,) in occupied_rows if folder_id is not None}
    return {"folders": _build_note_folder_tree(folders, folder_ids_with_notes)}


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
    return {"folder": _note_folder_to_dict(folder)}


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

        descendants = _collect_descendant_note_folder_ids(folder_id, db.query(NoteFolder).all())
        if target_parent_id in descendants:
            raise HTTPException(status_code=400, detail="Folder cannot be moved into its descendant")

    folder.parent_id = target_parent_id
    folder.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(folder)
    return {"folder": _note_folder_to_dict(folder)}


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
    return {"folder": _note_folder_to_dict(folder)}


@router.delete("/notes/folders/{folder_id}")
def delete_note_folder(folder_id: int, db: Session = Depends(get_db)) -> dict[str, int]:
    folder = db.query(NoteFolder).filter(NoteFolder.id == folder_id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    all_folders = db.query(NoteFolder).all()
    delete_folder_ids = _collect_descendant_note_folder_ids(folder_id, all_folders)

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
    return {"notes": [_note_to_dict(note) for note in notes]}


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

    file_path = persist_note_markdown(note_title, content, _note_folder_segments(db, folder_id))

    note = Note(
        note_id="",
        title=note_title,
        topic_key=_normalize_topic_key(note_title),
        summary="",
        content=content,
        structured_data={},
        paper_id=paper_id,
        session_id=session_id,
        folder_id=folder_id,
        file_path=file_path,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return {"note": _note_to_dict(note)}


@router.get("/notes/{note_id}")
def get_note(note_id: int, db: Session = Depends(get_db)) -> dict[str, dict[str, object]]:
    note = db.query(Note).filter(Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return {"note": _note_to_dict(note)}


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
        previous_topic_key = _normalize_topic_key(note.topic_key or previous_title)
        if not note.topic_key or note.topic_key == previous_topic_key:
            note.topic_key = _normalize_topic_key(note.title)
        if isinstance(note.structured_data, dict) and note.structured_data:
            next_structured_data = dict(note.structured_data)
            next_structured_data["title"] = note.title
            if next_structured_data.get("topic_key") == previous_topic_key:
                next_structured_data["topic_key"] = note.topic_key
            note.structured_data = next_structured_data
        if content is None:
            note.content = _sync_markdown_title(note.content, note.title)

    if title_changed:
        note.file_path = rename_note_markdown_file(note.file_path, note.title)

    note.updated_at = datetime.utcnow()
    overwrite_note_markdown(note.file_path, note.content)
    db.commit()
    db.refresh(note)
    return {"note": _note_to_dict(note)}


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
    note.file_path = move_note_file_to_segments(note.file_path, _note_folder_segments(db, target_folder_id))
    note.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(note)
    return {"note": _note_to_dict(note)}


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
