from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..db import ChatMessage, ChatSession, Folder, Paper, PaperPlacement, get_db
from ..services import extract_paper_metadata, move_pdf_file_to_segments, persist_uploaded_pdf
from .common import (
    build_folder_tree,
    collect_descendant_folder_ids,
    ensure_default_session,
    folder_segments,
    folder_to_dict,
    message_to_dict,
    paper_to_dict,
    session_to_dict,
)

router = APIRouter()


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

    file_path = persist_uploaded_pdf(pdf_bytes, filename, folder_segments=folder_segments(db, folder_id))
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

    ensure_default_session(db, paper.id)

    placement = PaperPlacement(paper_id=paper.id, folder_id=folder_id)
    db.add(placement)
    db.commit()

    return {"paper": paper_to_dict(paper)}


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
    return {"papers": [paper_to_dict(paper) for paper in papers]}


@router.get("/papers/{paper_id}")
def get_paper(paper_id: str, db: Session = Depends(get_db)) -> dict[str, dict[str, str | int]]:
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    return {"paper": paper_to_dict(paper)}


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
    return {"folders": build_folder_tree(folders, folder_ids_with_papers)}


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
    return {"folder": folder_to_dict(folder)}


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

        descendants = collect_descendant_folder_ids(folder_id, db.query(Folder).all())
        if target_parent_id in descendants:
            raise HTTPException(status_code=400, detail="Folder cannot be moved into its descendant")

    folder.parent_id = target_parent_id
    db.commit()
    db.refresh(folder)
    return {"folder": folder_to_dict(folder)}


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
    return {"folder": folder_to_dict(folder)}


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

    paper.file_path = move_pdf_file_to_segments(paper.file_path, folder_segments(db, target_folder_id))
    paper.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(paper)
    return {"paper": paper_to_dict(paper)}


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
    delete_folder_ids = collect_descendant_folder_ids(folder_id, all_folders)

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

    if session_id is not None:
        effective_session = (
            db.query(ChatSession)
            .filter(ChatSession.id == session_id, ChatSession.paper_id == paper_id)
            .first()
        )
        if not effective_session:
            raise HTTPException(status_code=404, detail="Session not found")
    else:
        effective_session = ensure_default_session(db, paper_id)

    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.paper_id == paper_id, ChatMessage.session_id == effective_session.id)
        .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
        .all()
    )

    return {"messages": [message_to_dict(message) for message in messages]}


@router.get("/papers/{paper_id}/sessions")
def list_paper_sessions(paper_id: str, db: Session = Depends(get_db)) -> dict[str, list[dict[str, str | int]]]:
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    ensure_default_session(db, paper_id)

    sessions = (
        db.query(ChatSession)
        .filter(ChatSession.paper_id == paper_id)
        .order_by(ChatSession.updated_at.desc(), ChatSession.id.desc())
        .all()
    )
    return {"sessions": [session_to_dict(session) for session in sessions]}


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
    return {"session": session_to_dict(new_session)}


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
    return {"session": session_to_dict(chat_session)}


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
        remaining = ensure_default_session(db, paper_id)

    db.query(Paper).filter(Paper.id == paper_id).update({"updated_at": datetime.utcnow()})
    db.commit()

    return {"deleted_session_id": session_id, "active_session_id": remaining.id}
