from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, JSON, DateTime, Float, ForeignKey, ForeignKeyConstraint, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .session import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, index=True, default=lambda: str(uuid4()))
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class UserMetadata(Base):
    __tablename__ = "user_metadata"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    locale: Mapped[str] = mapped_column(String(32), nullable=False, default="zh-CN")
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Asia/Shanghai")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class RefreshSession(Base):
    __tablename__ = "refresh_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    user_agent: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    ip_address: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class OneTimeToken(Base):
    __tablename__ = "one_time_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    purpose: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class AuthRateLimit(Base):
    __tablename__ = "auth_rate_limits"
    __table_args__ = (UniqueConstraint("action", "key_hash", name="uq_auth_rate_limit_action_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    action: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    window_started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    blocked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class UserOwnedMixin:
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)


class Paper(UserOwnedMixin, Base):
    __tablename__ = "papers"
    __table_args__ = (
        UniqueConstraint("user_id", "id", name="uq_papers_user_id_id"),
        ForeignKeyConstraint(
            ["user_id", "folder_id"], ["folders.user_id", "folders.id"]
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, index=True, default=lambda: str(uuid4()))
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    authors: Mapped[str] = mapped_column(String(1024), nullable=False, default="未知")
    research_topic: Mapped[str] = mapped_column(String(512), nullable=False, default="未标注")
    journal: Mapped[str] = mapped_column(String(512), nullable=False, default="未知")
    publication_date: Mapped[str] = mapped_column(String(64), nullable=False, default="未知")
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    folder_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class Folder(UserOwnedMixin, Base):
    __tablename__ = "folders"
    __table_args__ = (
        UniqueConstraint("user_id", "id", name="uq_folders_user_id_id"),
        ForeignKeyConstraint(
            ["user_id", "parent_id"], ["folders.user_id", "folders.id"], ondelete="CASCADE"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class ChatMessage(UserOwnedMixin, Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        UniqueConstraint("user_id", "id", name="uq_chat_messages_user_id_id"),
        ForeignKeyConstraint(
            ["user_id", "paper_id"], ["papers.user_id", "papers.id"], ondelete="CASCADE"
        ),
        ForeignKeyConstraint(
            ["user_id", "session_id"], ["chat_sessions.user_id", "chat_sessions.id"], ondelete="CASCADE"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    paper_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    session_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    quote: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class ChatSession(UserOwnedMixin, Base):
    __tablename__ = "chat_sessions"
    __table_args__ = (
        UniqueConstraint("user_id", "id", name="uq_chat_sessions_user_id_id"),
        ForeignKeyConstraint(
            ["user_id", "paper_id"], ["papers.user_id", "papers.id"], ondelete="CASCADE"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    paper_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="Session 1")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class NoteFolder(UserOwnedMixin, Base):
    __tablename__ = "note_folders"
    __table_args__ = (
        UniqueConstraint("user_id", "id", name="uq_note_folders_user_id_id"),
        ForeignKeyConstraint(
            ["user_id", "parent_id"], ["note_folders.user_id", "note_folders.id"], ondelete="CASCADE"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class Note(UserOwnedMixin, Base):
    __tablename__ = "notes"
    __table_args__ = (
        UniqueConstraint("user_id", "id", name="uq_notes_user_id_id"),
        ForeignKeyConstraint(
            ["user_id", "paper_id"], ["papers.user_id", "papers.id"]
        ),
        ForeignKeyConstraint(
            ["user_id", "session_id"], ["chat_sessions.user_id", "chat_sessions.id"]
        ),
        ForeignKeyConstraint(
            ["user_id", "folder_id"], ["note_folders.user_id", "note_folders.id"]
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    note_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    topic_key: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    cognitive_state: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    follow_up_questions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    dedupe_hints: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    paper_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    session_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
    )
    folder_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class KnowledgeUnit(UserOwnedMixin, Base):
    __tablename__ = "knowledge_units"
    __table_args__ = (
        UniqueConstraint("user_id", "id", name="uq_knowledge_units_user_id_id"),
        ForeignKeyConstraint(
            ["user_id", "paper_id"], ["papers.user_id", "papers.id"]
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    paper_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    canonical_key: Mapped[str] = mapped_column(String(255), nullable=False, default="", index=True)
    unit_type: Mapped[str] = mapped_column(String(32), nullable=False, default="concept")
    term: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    core_claim: Mapped[str] = mapped_column(Text, nullable=False, default="")
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    aliases: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    related_terms: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    slots: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class KnowledgeGraphEdge(UserOwnedMixin, Base):
    __tablename__ = "knowledge_graph_edges"
    __table_args__ = (
        UniqueConstraint("user_id", "from_unit_id", "relation", "to_unit_id", name="uq_knowledge_graph_edges"),
        ForeignKeyConstraint(
            ["user_id", "paper_id"], ["papers.user_id", "papers.id"]
        ),
        ForeignKeyConstraint(
            ["user_id", "from_unit_id"], ["knowledge_units.user_id", "knowledge_units.id"], ondelete="CASCADE"
        ),
        ForeignKeyConstraint(
            ["user_id", "to_unit_id"], ["knowledge_units.user_id", "knowledge_units.id"], ondelete="CASCADE"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    paper_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    from_unit_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )
    relation: Mapped[str] = mapped_column(String(64), nullable=False)
    to_unit_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class KnowledgeUnitNoteLink(UserOwnedMixin, Base):
    __tablename__ = "knowledge_unit_note_links"
    __table_args__ = (
        UniqueConstraint("user_id", "knowledge_unit_id", "note_id", name="uq_knowledge_unit_note_links"),
        ForeignKeyConstraint(
            ["user_id", "knowledge_unit_id"],
            ["knowledge_units.user_id", "knowledge_units.id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["user_id", "note_id"], ["notes.user_id", "notes.id"], ondelete="CASCADE"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    knowledge_unit_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )
    note_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
