import hashlib
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..db import AuthRateLimit

WINDOW = timedelta(minutes=15)
BLOCK = timedelta(minutes=15)
LIMITS = {
    "login": 10,
    "register": 5,
    "resend_verification": 5,
    "forgot_password": 5,
}


def _key_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def consume_attempt(db: Session, *, action: str, key: str, now: datetime | None = None) -> None:
    current = now or datetime.utcnow()
    hashed = _key_hash(key)
    row = db.query(AuthRateLimit).filter(AuthRateLimit.action == action, AuthRateLimit.key_hash == hashed).first()
    if row and row.blocked_until and row.blocked_until > current:
        raise HTTPException(status_code=429, detail="Too many requests")
    if not row:
        row = AuthRateLimit(action=action, key_hash=hashed, window_started_at=current, attempt_count=0)
        db.add(row)
    elif current - row.window_started_at >= WINDOW:
        row.window_started_at = current
        row.attempt_count = 0
        row.blocked_until = None
    row.attempt_count += 1
    if row.attempt_count > LIMITS.get(action, 10):
        row.blocked_until = current + BLOCK
        db.commit()
        raise HTTPException(status_code=429, detail="Too many requests")
    db.commit()


def clear_attempts(db: Session, *, action: str, key: str) -> None:
    db.query(AuthRateLimit).filter(
        AuthRateLimit.action == action,
        AuthRateLimit.key_hash == _key_hash(key),
    ).delete(synchronize_session=False)
    db.commit()
