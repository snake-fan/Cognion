from datetime import datetime, timedelta

from .models import (
    AuthRateLimit,
    ChatMessage,
    ChatSession,
    Folder,
    KnowledgeGraphEdge,
    KnowledgeUnit,
    KnowledgeUnitNoteLink,
    Note,
    NoteFolder,
    Paper,
    OneTimeToken,
    RefreshSession,
    User,
    UserMetadata,
)
from .session import Base, SessionLocal, engine


def cleanup_auth_records() -> None:
    from ..services.config import UNVERIFIED_USER_RETENTION_DAYS

    now = datetime.utcnow()
    db = SessionLocal()
    try:
        db.query(OneTimeToken).filter(OneTimeToken.expires_at <= now).delete(synchronize_session=False)
        db.query(RefreshSession).filter(RefreshSession.expires_at <= now).delete(synchronize_session=False)
        db.query(AuthRateLimit).filter(
            AuthRateLimit.window_started_at < now - timedelta(days=1)
        ).delete(synchronize_session=False)
        db.query(User).filter(
            User.email_verified_at.is_(None),
            User.updated_at < now - timedelta(days=UNVERIFIED_USER_RETENTION_DAYS),
        ).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def init_database() -> None:
    Base.metadata.create_all(
        bind=engine,
        tables=[
            User.__table__,
            UserMetadata.__table__,
            RefreshSession.__table__,
            OneTimeToken.__table__,
            AuthRateLimit.__table__,
            Folder.__table__,
            Paper.__table__,
            ChatMessage.__table__,
            ChatSession.__table__,
            NoteFolder.__table__,
            Note.__table__,
            KnowledgeUnit.__table__,
            KnowledgeGraphEdge.__table__,
            KnowledgeUnitNoteLink.__table__,
        ],
    )
    cleanup_auth_records()
from datetime import datetime, timedelta
