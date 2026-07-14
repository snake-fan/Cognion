from datetime import datetime, timedelta
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.auth.security import create_access_token, decode_access_token, hash_password
from backend.app.db import Base, Folder, Paper, User, get_db
from backend.app.routes.auth import router as auth_router
from backend.app.routes.papers import router as papers_router
from backend.app.routes.users import router as users_router
from backend.app.auth.dependencies import get_current_user
from fastapi import Depends


def build_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    event.listen(engine, "connect", lambda connection, _record: connection.execute("PRAGMA foreign_keys=ON"))
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(engine)
    app = FastAPI()
    app.include_router(auth_router, prefix="/api")
    app.include_router(users_router, prefix="/api")
    app.include_router(papers_router, prefix="/api", dependencies=[Depends(get_current_user)])

    def override_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    return TestClient(app), TestingSession


def test_registration_verification_login_refresh_and_tenant_filtering():
    client, Session = build_client()
    with patch("backend.app.routes.auth._send_action_email") as send_email:
        response = client.post("/api/auth/register", json={"email": " Alice@Example.com ", "password": "abcdefgh"})
        assert response.status_code == 202
        verification_token = send_email.call_args.kwargs["token"]

    assert client.post("/api/auth/login", json={"email": "alice@example.com", "password": "abcdefgh"}).status_code == 401
    assert client.post("/api/auth/verify-email", json={"token": verification_token}).status_code == 200
    login = client.post("/api/auth/login", json={"email": "alice@example.com", "password": "abcdefgh"})
    assert login.status_code == 200
    access_token = login.json()["access_token"]

    db = Session()
    alice = db.query(User).filter(User.email == "alice@example.com").one()
    bob = User(email="bob@example.com", password_hash=hash_password("abcdefgh"), email_verified_at=datetime.utcnow())
    db.add(bob)
    db.commit()
    db.info["user_id"] = alice.id
    db.add(Folder(name="Alice folder"))
    db.commit()
    db.info["user_id"] = bob.id
    bob_folder = Folder(name="Bob folder")
    db.add(bob_folder)
    db.commit()
    bob_folder_id = bob_folder.id
    db.info["user_id"] = alice.id
    db.add(
        Paper(
            title="Cross-user paper",
            authors="Author",
            research_topic="Topic",
            journal="Journal",
            publication_date="2026",
            original_filename="paper.pdf",
            file_path="/tmp/paper.pdf",
            folder_id=bob_folder_id,
        )
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
    else:
        raise AssertionError("Database allowed a cross-user parent relationship")
    db.close()

    tree = client.get("/api/folders/tree", headers={"Authorization": f"Bearer {access_token}"})
    assert tree.status_code == 200
    assert [folder["name"] for folder in tree.json()["folders"]] == ["Alice folder"]

    refreshed = client.post("/api/auth/refresh")
    assert refreshed.status_code == 200
    assert refreshed.json()["access_token"] != access_token
    assert client.post("/api/auth/logout").status_code == 204
    assert client.post("/api/auth/refresh").status_code == 401

    next_login = client.post("/api/auth/login", json={"email": "alice@example.com", "password": "abcdefgh"})
    delete_response = client.request(
        "DELETE",
        "/api/users/me",
        headers={"Authorization": f"Bearer {next_login.json()['access_token']}"},
        json={"password": "abcdefgh"},
    )
    assert delete_response.status_code == 200
    assert client.post("/api/auth/refresh").status_code == 401
    db = Session()
    assert db.query(User).filter(User.email == "alice@example.com").first() is None
    db.close()


def test_access_token_rejects_expired_token():
    token = create_access_token("user-1", now=datetime.utcnow() - timedelta(hours=1))
    try:
        decode_access_token(token)
    except ValueError:
        pass
    else:
        raise AssertionError("Expired token was accepted")
