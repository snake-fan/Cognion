from .models import (
    AgentRun,
    ChatMessage,
    ChatSession,
    Folder,
    GraphUpdateLog,
    KnowledgeGraphEdge,
    KnowledgeUnit,
    KnowledgeUnitNoteLink,
    Note,
    NoteUnitCandidate,
    NoteFolder,
    Paper,
    UnitCanonicalizationDecision,
    UnitRelationDecision,
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
            AgentRun.__table__,
            Note.__table__,
            KnowledgeUnit.__table__,
            KnowledgeGraphEdge.__table__,
            KnowledgeUnitNoteLink.__table__,
            NoteUnitCandidate.__table__,
            UnitCanonicalizationDecision.__table__,
            UnitRelationDecision.__table__,
            GraphUpdateLog.__table__,
        ],
    )
