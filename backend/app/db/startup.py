from .models import (
    ChatMessage,
    ChatSession,
    Folder,
    KnowledgeGraphEdge,
    KnowledgeUnit,
    KnowledgeUnitNoteLink,
    Note,
    NoteFolder,
    Paper,
)
from .session import Base, engine


def init_database() -> None:
    Base.metadata.create_all(
        bind=engine,
        tables=[
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
