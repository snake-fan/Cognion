import os
from collections.abc import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session, declarative_base, sessionmaker

load_dotenv()

DATABASE_USER = os.getenv("DATABASE_USER", "postgres")
DATABASE_PASSWORD = os.getenv("DATABASE_PASSWORD")
DATABASE_HOST = os.getenv("DATABASE_HOST", "127.0.0.1")
DATABASE_PORT = int(os.getenv("DATABASE_PORT", "5432"))
DATABASE_NAME = os.getenv("DATABASE_NAME", "cognion_db")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    DATABASE_URL = str(
        URL.create(
            drivername="postgresql+psycopg2",
            username=DATABASE_USER,
            password=DATABASE_PASSWORD,
            host=DATABASE_HOST,
            port=DATABASE_PORT,
            database=DATABASE_NAME,
        )
    )

engine = create_engine(DATABASE_URL, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_database() -> None:
    from .models import ChatMessage, ChatSession, Folder, Note, NoteFolder, Paper, PaperPlacement

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
        ],
    )

    inspector = inspect(engine)
    chat_message_columns = {column["name"] for column in inspector.get_columns("chat_messages")}
    note_columns = {column["name"] for column in inspector.get_columns("notes")}

    with engine.begin() as connection:
        if "session_id" not in chat_message_columns:
            connection.execute(text("ALTER TABLE chat_messages ADD COLUMN session_id INTEGER"))
            connection.execute(
                text(
                    "ALTER TABLE chat_messages "
                    "ADD CONSTRAINT fk_chat_messages_session_id "
                    "FOREIGN KEY (session_id) REFERENCES chat_sessions (id) ON DELETE CASCADE"
                )
            )
            connection.execute(text("CREATE INDEX IF NOT EXISTS ix_chat_messages_session_id ON chat_messages (session_id)"))

        # Backfill legacy rows into one default session per paper so historical chats remain visible.
        rows = connection.execute(
            text(
                "SELECT DISTINCT paper_id "
                "FROM chat_messages "
                "WHERE session_id IS NULL"
            )
        ).fetchall()

        for (paper_id,) in rows:
            existing_session = connection.execute(
                text(
                    "SELECT id FROM chat_sessions "
                    "WHERE paper_id = :paper_id "
                    "ORDER BY id ASC "
                    "LIMIT 1"
                ),
                {"paper_id": paper_id},
            ).fetchone()

            if existing_session:
                session_id = existing_session[0]
            else:
                session_id = connection.execute(
                    text(
                        "INSERT INTO chat_sessions (paper_id, name, created_at, updated_at) "
                        "VALUES (:paper_id, :name, NOW(), NOW()) "
                        "RETURNING id"
                    ),
                    {"paper_id": paper_id, "name": "Session 1"},
                ).scalar_one()

            connection.execute(
                text(
                    "UPDATE chat_messages "
                    "SET session_id = :session_id "
                    "WHERE paper_id = :paper_id AND session_id IS NULL"
                ),
                {"session_id": session_id, "paper_id": paper_id},
            )

        if "note_id" not in note_columns:
            connection.execute(text("ALTER TABLE notes ADD COLUMN note_id VARCHAR(64)"))
        if "topic_key" not in note_columns:
            connection.execute(text("ALTER TABLE notes ADD COLUMN topic_key VARCHAR(255)"))
        if "summary" not in note_columns:
            connection.execute(text("ALTER TABLE notes ADD COLUMN summary TEXT"))
        if "structured_data" not in note_columns:
            connection.execute(text("ALTER TABLE notes ADD COLUMN structured_data JSON"))

        connection.execute(text("UPDATE notes SET note_id = '' WHERE note_id IS NULL"))
        connection.execute(text("UPDATE notes SET topic_key = '' WHERE topic_key IS NULL"))
        connection.execute(text("UPDATE notes SET summary = '' WHERE summary IS NULL"))
        connection.execute(text("UPDATE notes SET structured_data = '{}'::json WHERE structured_data IS NULL"))
