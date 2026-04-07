import json
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ChatMessage, ChatSession, Paper
from ..services import answer_with_context, answer_with_context_stream
from .common import ensure_default_session

router = APIRouter()


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
            chat_session = ensure_default_session(db, paper_id)

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
