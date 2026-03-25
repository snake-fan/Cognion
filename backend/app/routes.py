from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .database import get_db
from .models import ChatMessage, Paper
from .services import answer_with_context, extract_paper_metadata, persist_uploaded_pdf

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


def _message_to_dict(message: ChatMessage) -> dict[str, str | int]:
    return {
        "id": message.id,
        "paper_id": message.paper_id,
        "role": message.role,
        "content": message.content,
        "quote": message.quote,
        "created_at": message.created_at.isoformat() if isinstance(message.created_at, datetime) else "",
    }


@router.post("/ask")
async def ask_about_quote(
    question: str = Form(...),
    quote: str = Form(default=""),
    paper_id: int | None = Form(default=None),
    pdf_file: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    if paper_id is not None:
        paper = db.query(Paper).filter(Paper.id == paper_id).first()
        if not paper:
            raise HTTPException(status_code=404, detail="Paper not found")

    pdf_bytes = await pdf_file.read() if pdf_file else None
    response_text = await answer_with_context(
        question=question,
        quote=quote,
        pdf_bytes=pdf_bytes,
        pdf_filename=pdf_file.filename if pdf_file else None,
    )

    if paper_id is not None:
        user_message = ChatMessage(
            paper_id=paper_id,
            role="user",
            content=question,
            quote=quote or "",
        )
        assistant_message = ChatMessage(
            paper_id=paper_id,
            role="assistant",
            content=response_text,
            quote="",
        )

        db.add(user_message)
        db.add(assistant_message)
        db.query(Paper).filter(Paper.id == paper_id).update({"updated_at": datetime.utcnow()})
        db.commit()

    return {"answer": response_text}


@router.post("/papers/upload")
async def upload_paper(
    pdf_file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict[str, dict[str, str | int]]:
    filename = pdf_file.filename or "paper.pdf"
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    pdf_bytes = await pdf_file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="Uploaded PDF is empty")

    file_path = persist_uploaded_pdf(pdf_bytes, filename)
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

    return {"paper": _paper_to_dict(paper)}


@router.get("/papers")
def list_papers(db: Session = Depends(get_db)) -> dict[str, list[dict[str, str | int]]]:
    papers = db.query(Paper).order_by(Paper.updated_at.desc()).all()
    return {"papers": [_paper_to_dict(paper) for paper in papers]}


@router.get("/papers/{paper_id}")
def get_paper(paper_id: int, db: Session = Depends(get_db)) -> dict[str, dict[str, str | int]]:
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    return {"paper": _paper_to_dict(paper)}


@router.get("/papers/{paper_id}/file")
def get_paper_file(paper_id: int, db: Session = Depends(get_db)) -> FileResponse:
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


@router.get("/papers/{paper_id}/messages")
def list_paper_messages(paper_id: int, db: Session = Depends(get_db)) -> dict[str, list[dict[str, str | int]]]:
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.paper_id == paper_id)
        .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
        .all()
    )

    return {"messages": [_message_to_dict(message) for message in messages]}
