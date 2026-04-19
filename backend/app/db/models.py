from datetime import datetime
from uuid import uuid4

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .session import Base


class Paper(Base):
    __tablename__ = "papers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, index=True, default=lambda: str(uuid4()))
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    authors: Mapped[str] = mapped_column(String(1024), nullable=False, default="未知")
    research_topic: Mapped[str] = mapped_column(String(512), nullable=False, default="未标注")
    journal: Mapped[str] = mapped_column(String(512), nullable=False, default="未知")
    publication_date: Mapped[str] = mapped_column(String(64), nullable=False, default="未知")
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class Folder(Base):
    __tablename__ = "folders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("folders.id", ondelete="CASCADE"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class PaperPlacement(Base):
    __tablename__ = "paper_placements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    paper_id: Mapped[str] = mapped_column(ForeignKey("papers.id", ondelete="CASCADE"), nullable=False, unique=True)
    folder_id: Mapped[int | None] = mapped_column(ForeignKey("folders.id", ondelete="CASCADE"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    paper_id: Mapped[str] = mapped_column(ForeignKey("papers.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id: Mapped[int | None] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    quote: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    paper_id: Mapped[str] = mapped_column(ForeignKey("papers.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="Session 1")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class NoteFolder(Base):
    __tablename__ = "note_folders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("note_folders.id", ondelete="CASCADE"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    note_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    topic_key: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    structured_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    paper_id: Mapped[str | None] = mapped_column(ForeignKey("papers.id", ondelete="SET NULL"), nullable=True, index=True)
    session_id: Mapped[int | None] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    folder_id: Mapped[int | None] = mapped_column(ForeignKey("note_folders.id", ondelete="SET NULL"), nullable=True)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class KnowledgeUnit(Base):
    __tablename__ = "knowledge_units"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    paper_id: Mapped[str | None] = mapped_column(ForeignKey("papers.id", ondelete="SET NULL"), nullable=True, index=True)
    canonical_key: Mapped[str] = mapped_column(String(255), nullable=False, default="", index=True)
    unit_type: Mapped[str] = mapped_column(String(32), nullable=False, default="concept")
    term: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    core_claim: Mapped[str] = mapped_column(Text, nullable=False, default="")
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    aliases: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    semantic_fingerprint: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class KnowledgeGraphEdge(Base):
    __tablename__ = "knowledge_graph_edges"
    __table_args__ = (
        UniqueConstraint("from_unit_id", "relation", "to_unit_id", name="uq_knowledge_graph_edges"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    paper_id: Mapped[str | None] = mapped_column(ForeignKey("papers.id", ondelete="SET NULL"), nullable=True, index=True)
    from_unit_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_units.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    relation: Mapped[str] = mapped_column(String(64), nullable=False)
    to_unit_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_units.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class KnowledgeUnitNoteLink(Base):
    __tablename__ = "knowledge_unit_note_links"
    __table_args__ = (
        UniqueConstraint("knowledge_unit_id", "note_id", name="uq_knowledge_unit_note_links"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    knowledge_unit_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_units.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    note_id: Mapped[int] = mapped_column(ForeignKey("notes.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True, default="")
    pipeline_name: Mapped[str] = mapped_column(String(128), nullable=False, default="session_notes_pipeline")
    paper_id: Mapped[str | None] = mapped_column(ForeignKey("papers.id", ondelete="SET NULL"), nullable=True, index=True)
    session_id: Mapped[int | None] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="completed")
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class NoteUnitCandidate(Base):
    __tablename__ = "note_unit_candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    agent_run_id: Mapped[int] = mapped_column(ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    note_ref: Mapped[str] = mapped_column(String(64), nullable=False, default="", index=True)
    note_id: Mapped[int | None] = mapped_column(ForeignKey("notes.id", ondelete="SET NULL"), nullable=True, index=True)
    unit_ref: Mapped[str] = mapped_column(String(64), nullable=False, default="", index=True)
    candidate_key: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class UnitCanonicalizationDecision(Base):
    __tablename__ = "unit_canonicalization_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    agent_run_id: Mapped[int] = mapped_column(ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    note_ref: Mapped[str] = mapped_column(String(64), nullable=False, default="", index=True)
    note_id: Mapped[int | None] = mapped_column(ForeignKey("notes.id", ondelete="SET NULL"), nullable=True, index=True)
    source_unit_ref: Mapped[str] = mapped_column(String(64), nullable=False, default="", index=True)
    action: Mapped[str] = mapped_column(String(32), nullable=False, default="create_new")
    target_unit_id: Mapped[int | None] = mapped_column(
        ForeignKey("knowledge_units.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    target_canonical_key: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class UnitRelationDecision(Base):
    __tablename__ = "unit_relation_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    agent_run_id: Mapped[int] = mapped_column(ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    note_ref: Mapped[str] = mapped_column(String(64), nullable=False, default="", index=True)
    note_id: Mapped[int | None] = mapped_column(ForeignKey("notes.id", ondelete="SET NULL"), nullable=True, index=True)
    from_unit_ref: Mapped[str] = mapped_column(String(64), nullable=False, default="", index=True)
    relation_type: Mapped[str] = mapped_column(String(64), nullable=False, default="related_to")
    to_unit_ref: Mapped[str] = mapped_column(String(255), nullable=False, default="", index=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class GraphUpdateLog(Base):
    __tablename__ = "graph_update_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    agent_run_id: Mapped[int] = mapped_column(ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    note_ref: Mapped[str] = mapped_column(String(64), nullable=False, default="", index=True)
    note_id: Mapped[int | None] = mapped_column(ForeignKey("notes.id", ondelete="SET NULL"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="applied")
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    error: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
