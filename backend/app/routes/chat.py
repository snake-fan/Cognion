import asyncio
import json
import re
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..db import ChatMessage, ChatSession, Paper, get_db
from ..auth.context import set_current_user_id
from ..services import answer_with_context, answer_with_context_stream, generate_session_name
from ..services.cognitive_context import collect_cognitive_context_candidates
from .common import ensure_default_session, session_to_dict

router = APIRouter()

AUTO_SESSION_NAME_RE = re.compile(r"^Session\s+\d+$", re.IGNORECASE)


def _message_size(message: ChatMessage) -> int:
    return len(message.content or "") + len(message.quote or "")


def _recent_conversation_history(
    db: Session,
    *,
    paper_id: str,
    session_id: int | None,
    limit: int = 12,
    max_chars: int = 6000,
) -> list[dict[str, str]]:
    query = db.query(ChatMessage).filter(ChatMessage.paper_id == paper_id)
    if session_id is None:
        query = query.filter(ChatMessage.session_id.is_(None))
    else:
        query = query.filter(ChatMessage.session_id == session_id)

    newest_messages = query.order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc()).limit(limit).all()
    selected: list[ChatMessage] = []
    total_chars = 0
    for message in newest_messages:
        message_chars = _message_size(message)
        if selected and total_chars + message_chars > max_chars:
            continue
        selected.append(message)
        total_chars += message_chars

    return [
        {
            "role": message.role,
            "content": message.content,
            "quote": message.quote or "",
        }
        for message in reversed(selected)
    ]


def _collect_cognitive_context_candidates(
    db: Session,
    *,
    question: str,
    quote: str,
    paper_id: str | None,
    session_id: int | None,
) -> list[dict[str, object]]:
    if not paper_id:
        return []
    try:
        return collect_cognitive_context_candidates(
            db,
            question=question,
            quote=quote,
            paper_id=paper_id,
            session_id=session_id,
        )
    except Exception:
        return []


def _is_auto_session_name(name: str) -> bool:
    return bool(AUTO_SESSION_NAME_RE.fullmatch((name or "").strip()))


def _create_session_name_task(
    *,
    chat_session: ChatSession | None,
    conversation_history: list[dict[str, str]],
    question: str,
    quote: str,
    paper: Paper | None,
    paper_id: str | None,
    session_id: int | None,
) -> asyncio.Task[str] | None:
    if chat_session is None or conversation_history or not _is_auto_session_name(chat_session.name):
        return None

    return asyncio.create_task(
        generate_session_name(
            question=question,
            quote=quote,
            paper_title=paper.title if paper else "",
            paper_topic=paper.research_topic if paper else "",
            paper_id=paper_id,
            session_id=str(session_id) if session_id is not None else None,
        )
    )


async def _resolve_session_name_task(task: asyncio.Task[str] | None) -> str | None:
    if task is None:
        return None
    try:
        generated_name = await task
    except Exception:
        return None
    return generated_name.strip() or None


def _discard_session_name_task(task: asyncio.Task[str] | None) -> None:
    if task is None:
        return
    if task.done():
        try:
            task.result()
        except BaseException:
            pass
        return
    task.cancel()


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
    set_current_user_id(str(db.info["user_id"]))
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
    effective_session_id = chat_session.id if chat_session else None
    conversation_history = (
        _recent_conversation_history(db, paper_id=paper_id, session_id=effective_session_id)
        if paper_id is not None
        else []
    )
    cognitive_context_candidates = _collect_cognitive_context_candidates(
        db,
        question=question,
        quote=quote,
        paper_id=paper_id,
        session_id=effective_session_id,
    )
    session_name_task = _create_session_name_task(
        chat_session=chat_session,
        conversation_history=conversation_history,
        question=question,
        quote=quote,
        paper=paper,
        paper_id=paper_id,
        session_id=effective_session_id,
    )

    def persist_chat_turn(answer_text: str, generated_session_name: str | None = None) -> dict[str, str | int] | None:
        if paper_id is None:
            return None

        user_message = ChatMessage(
            paper_id=paper_id,
            session_id=effective_session_id,
            role="user",
            content=question,
            quote=quote or "",
        )
        assistant_message = ChatMessage(
            paper_id=paper_id,
            session_id=effective_session_id,
            role="assistant",
            content=answer_text,
            quote="",
        )

        db.add(user_message)
        db.add(assistant_message)
        persisted_session: ChatSession | None = None
        if effective_session_id is not None:
            persisted_session = (
                db.query(ChatSession)
                .filter(ChatSession.id == effective_session_id, ChatSession.paper_id == paper_id)
                .first()
            )
        if persisted_session is not None:
            if generated_session_name:
                if _is_auto_session_name(persisted_session.name):
                    persisted_session.name = generated_session_name
            persisted_session.updated_at = datetime.utcnow()
        db.query(Paper).filter(Paper.id == paper_id).update({"updated_at": datetime.utcnow()})
        db.commit()
        if persisted_session is not None:
            db.refresh(persisted_session)
            return session_to_dict(persisted_session)
        return None

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
                    paper_id=paper_id,
                    session_id=str(effective_session_id) if effective_session_id is not None else None,
                    conversation_history=conversation_history,
                    cognitive_context_candidates=cognitive_context_candidates,
                ):
                    if not delta:
                        continue

                    answer_parts.append(delta)
                    yield f"event: chunk\ndata: {json.dumps({'delta': delta}, ensure_ascii=False)}\n\n"

                answer_text = "".join(answer_parts)
                generated_session_name = await _resolve_session_name_task(session_name_task)
                session_payload = persist_chat_turn(answer_text, generated_session_name)
                done_payload: dict[str, object] = {"answer": answer_text}
                if session_payload is not None:
                    done_payload["session"] = session_payload
                yield f"event: done\ndata: {json.dumps(done_payload, ensure_ascii=False)}\n\n"
            except Exception as exc:  # pragma: no cover - runtime path
                _discard_session_name_task(session_name_task)
                yield f"event: error\ndata: {json.dumps({'detail': str(exc)}, ensure_ascii=False)}\n\n"

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    try:
        response_text = await answer_with_context(
            question=question,
            quote=quote,
            pdf_bytes=pdf_bytes,
            pdf_filename=effective_pdf_filename,
            local_pdf_path=effective_pdf_path,
            paper_id=paper_id,
            session_id=str(effective_session_id) if effective_session_id is not None else None,
            conversation_history=conversation_history,
            cognitive_context_candidates=cognitive_context_candidates,
        )
    except Exception:
        _discard_session_name_task(session_name_task)
        raise

    generated_session_name = await _resolve_session_name_task(session_name_task)
    session_payload = persist_chat_turn(response_text, generated_session_name)

    payload: dict[str, object] = {"answer": response_text}
    if session_payload is not None:
        payload["session"] = session_payload
    return payload
