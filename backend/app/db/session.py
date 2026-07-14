import os
from collections.abc import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy import event
from sqlalchemy.orm import Session, declarative_base, sessionmaker, with_loader_criteria

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


@event.listens_for(Session, "do_orm_execute")
def _apply_user_scope(execute_state) -> None:
    user_id = execute_state.session.info.get("user_id")
    if not user_id or execute_state.execution_options.get("skip_user_scope"):
        return
    from .models import UserOwnedMixin

    execute_state.statement = execute_state.statement.options(
        with_loader_criteria(
            UserOwnedMixin,
            lambda model: model.user_id == user_id,
            include_aliases=True,
        )
    )


@event.listens_for(Session, "before_flush")
def _enforce_new_object_ownership(session: Session, _flush_context, _instances) -> None:
    user_id = session.info.get("user_id")
    if not user_id:
        return
    from .models import UserOwnedMixin

    for instance in session.new:
        if not isinstance(instance, UserOwnedMixin):
            continue
        if getattr(instance, "user_id", None) not in (None, user_id):
            raise ValueError("Cross-user resource ownership is not allowed")
        instance.user_id = user_id


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
