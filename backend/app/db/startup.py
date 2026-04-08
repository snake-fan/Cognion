from .models import (
    ChatMessage,
    ChatSession,
    Folder,
    KnowledgeGraphEdge,
    KnowledgeGraphNode,
    KnowledgeUnit,
    KnowledgeUnitNodeLink,
    KnowledgeUnitNoteLink,
    Note,
    NoteFolder,
    Paper,
    PaperPlacement,
)
from .session import Base, engine


def init_database() -> None:
    Base.metadata.create_all(
        bind=engine,
        tables=[
            Paper.__table__,
            ChatMessage.__table__,
            ChatSession.__table__,
            Folder.__table__,
            PaperPlacement.__table__,
            NoteFolder.__table__,
            Note.__table__,
            KnowledgeUnit.__table__,
            KnowledgeGraphNode.__table__,
            KnowledgeGraphEdge.__table__,
            KnowledgeUnitNoteLink.__table__,
            KnowledgeUnitNodeLink.__table__,
        ],
    )
