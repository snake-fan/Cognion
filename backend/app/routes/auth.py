from datetime import datetime, timedelta
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth.dependencies import get_current_user
from ..auth.mailer import MailNotConfiguredError, send_email
from ..auth.rate_limit import clear_attempts, consume_attempt
from ..auth.security import (
    create_access_token,
    hash_password,
    hash_token,
    new_random_token,
    normalize_email,
    validate_password,
    verify_password,
)
from ..db import OneTimeToken, RefreshSession, User, UserMetadata, get_db
from ..services.config import (
    FRONTEND_BASE_URL,
    IS_PRODUCTION,
    ONE_TIME_TOKEN_MINUTES,
    REFRESH_TOKEN_DAYS,
)

router = APIRouter(prefix="/auth", tags=["auth"])
REFRESH_COOKIE = "cognion_refresh"


class EmailPasswordBody(BaseModel):
    email: str
    password: str


class EmailBody(BaseModel):
    email: str


class TokenBody(BaseModel):
    token: str


class ResetPasswordBody(TokenBody):
    new_password: str


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _rate_limit(db: Session, request: Request, action: str, email: str) -> None:
    consume_attempt(db, action=action, key=f"ip:{_client_ip(request)}")
    consume_attempt(db, action=action, key=f"email:{email}")


def _user_payload(db: Session, user: User) -> dict[str, object]:
    metadata = db.query(UserMetadata).filter(UserMetadata.user_id == user.id).first()
    return {
        "id": user.id,
        "email": user.email,
        "email_verified": user.email_verified_at is not None,
        "metadata": {
            "display_name": metadata.display_name if metadata else "",
            "avatar_url": metadata.avatar_url if metadata else None,
            "locale": metadata.locale if metadata else "zh-CN",
            "timezone": metadata.timezone if metadata else "Asia/Shanghai",
        },
    }


def _replace_one_time_token(db: Session, user: User, purpose: str) -> str:
    now = datetime.utcnow()
    user.updated_at = now
    db.query(OneTimeToken).filter(
        OneTimeToken.user_id == user.id,
        OneTimeToken.purpose == purpose,
        OneTimeToken.used_at.is_(None),
    ).update({"used_at": now}, synchronize_session=False)
    raw_token = new_random_token()
    db.add(
        OneTimeToken(
            user_id=user.id,
            purpose=purpose,
            token_hash=hash_token(raw_token),
            expires_at=now + timedelta(minutes=ONE_TIME_TOKEN_MINUTES),
        )
    )
    db.commit()
    return raw_token


def _send_action_email(user: User, *, purpose: str, token: str) -> None:
    action = "verify-email" if purpose == "verify_email" else "reset-password"
    url = f"{FRONTEND_BASE_URL}/?{urlencode({'action': action, 'token': token})}"
    if purpose == "verify_email":
        subject = "Verify your Cognion email"
        body = f"Verify your Cognion email by opening this link within {ONE_TIME_TOKEN_MINUTES} minutes:\n\n{url}"
    else:
        subject = "Reset your Cognion password"
        body = f"Reset your Cognion password by opening this link within {ONE_TIME_TOKEN_MINUTES} minutes:\n\n{url}"
    send_email(recipient=user.email, subject=subject, body=body)


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=token,
        max_age=REFRESH_TOKEN_DAYS * 24 * 60 * 60,
        httponly=True,
        secure=IS_PRODUCTION,
        samesite="lax",
        path="/api/auth",
    )


def _new_refresh_session(db: Session, user: User, request: Request) -> str:
    raw_token = new_random_token()
    db.add(
        RefreshSession(
            user_id=user.id,
            token_hash=hash_token(raw_token),
            user_agent=(request.headers.get("user-agent") or "")[:512],
            ip_address=_client_ip(request)[:64],
            expires_at=datetime.utcnow() + timedelta(days=REFRESH_TOKEN_DAYS),
        )
    )
    db.commit()
    return raw_token


@router.post("/register", status_code=202)
def register(body: EmailPasswordBody, request: Request, db: Session = Depends(get_db)) -> dict[str, str]:
    try:
        email = normalize_email(body.email)
        password_hash = hash_password(body.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    _rate_limit(db, request, "register", email)

    user = db.query(User).filter(User.email == email).first()
    if user and user.email_verified_at is not None:
        return {"message": "If registration can continue, a verification email has been sent."}
    if not user:
        user = User(email=email, password_hash=password_hash)
        db.add(user)
        db.flush()
        db.add(UserMetadata(user_id=user.id, display_name=email.split("@", 1)[0]))
        db.commit()
        db.refresh(user)

    token = _replace_one_time_token(db, user, "verify_email")
    try:
        _send_action_email(user, purpose="verify_email", token=token)
    except MailNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None
    return {"message": "If registration can continue, a verification email has been sent."}


@router.post("/verify-email")
def verify_email(body: TokenBody, db: Session = Depends(get_db)) -> dict[str, str]:
    now = datetime.utcnow()
    token = db.query(OneTimeToken).filter(
        OneTimeToken.token_hash == hash_token(body.token),
        OneTimeToken.purpose == "verify_email",
        OneTimeToken.used_at.is_(None),
        OneTimeToken.expires_at > now,
    ).first()
    if not token:
        raise HTTPException(status_code=400, detail="Invalid or expired verification token")
    user = db.query(User).filter(User.id == token.user_id, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired verification token")
    token.used_at = now
    user.email_verified_at = now
    db.commit()
    return {"message": "Email verified. Please sign in."}


@router.post("/resend-verification", status_code=202)
def resend_verification(body: EmailBody, request: Request, db: Session = Depends(get_db)) -> dict[str, str]:
    try:
        email = normalize_email(body.email)
    except ValueError:
        email = body.email.strip().lower()
    _rate_limit(db, request, "resend_verification", email)
    user = db.query(User).filter(User.email == email, User.email_verified_at.is_(None)).first()
    if user:
        token = _replace_one_time_token(db, user, "verify_email")
        try:
            _send_action_email(user, purpose="verify_email", token=token)
        except MailNotConfiguredError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from None
    return {"message": "If the address is eligible, a verification email has been sent."}


@router.post("/login")
def login(body: EmailPasswordBody, request: Request, response: Response, db: Session = Depends(get_db)) -> dict[str, object]:
    try:
        email = normalize_email(body.email)
    except ValueError:
        email = body.email.strip().lower()
    _rate_limit(db, request, "login", email)
    user = db.query(User).filter(User.email == email, User.is_active.is_(True)).first()
    if not user or user.email_verified_at is None or not verify_password(user.password_hash, body.password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    clear_attempts(db, action="login", key=f"email:{email}")
    clear_attempts(db, action="login", key=f"ip:{_client_ip(request)}")
    refresh_token = _new_refresh_session(db, user, request)
    _set_refresh_cookie(response, refresh_token)
    return {"access_token": create_access_token(user.id), "token_type": "bearer", "user": _user_payload(db, user)}


@router.post("/refresh")
def refresh(request: Request, response: Response, db: Session = Depends(get_db)) -> dict[str, object]:
    raw_token = request.cookies.get(REFRESH_COOKIE, "")
    now = datetime.utcnow()
    session = db.query(RefreshSession).filter(RefreshSession.token_hash == hash_token(raw_token)).first() if raw_token else None
    if not session or session.expires_at <= now:
        response.delete_cookie(REFRESH_COOKIE, path="/api/auth")
        raise HTTPException(status_code=401, detail="Invalid refresh session")
    if session.revoked_at is not None:
        db.query(RefreshSession).filter(RefreshSession.user_id == session.user_id).update(
            {"revoked_at": now}, synchronize_session=False
        )
        db.commit()
        response.delete_cookie(REFRESH_COOKIE, path="/api/auth")
        raise HTTPException(status_code=401, detail="Refresh token reuse detected")
    user = db.query(User).filter(User.id == session.user_id, User.is_active.is_(True)).first()
    if not user or user.email_verified_at is None:
        raise HTTPException(status_code=401, detail="Invalid refresh session")
    session.revoked_at = now
    next_token = _new_refresh_session(db, user, request)
    _set_refresh_cookie(response, next_token)
    return {"access_token": create_access_token(user.id), "token_type": "bearer", "user": _user_payload(db, user)}


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> Response:
    raw_token = request.cookies.get(REFRESH_COOKIE, "")
    if raw_token:
        db.query(RefreshSession).filter(
            RefreshSession.token_hash == hash_token(raw_token), RefreshSession.revoked_at.is_(None)
        ).update({"revoked_at": datetime.utcnow()}, synchronize_session=False)
        db.commit()
    response.delete_cookie(REFRESH_COOKIE, path="/api/auth")
    response.status_code = 204
    return response


@router.post("/forgot-password", status_code=202)
def forgot_password(body: EmailBody, request: Request, db: Session = Depends(get_db)) -> dict[str, str]:
    try:
        email = normalize_email(body.email)
    except ValueError:
        email = body.email.strip().lower()
    _rate_limit(db, request, "forgot_password", email)
    user = db.query(User).filter(User.email == email, User.email_verified_at.isnot(None), User.is_active.is_(True)).first()
    if user:
        token = _replace_one_time_token(db, user, "reset_password")
        try:
            _send_action_email(user, purpose="reset_password", token=token)
        except MailNotConfiguredError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from None
    return {"message": "If the address exists, a password reset email has been sent."}


@router.post("/reset-password")
def reset_password(body: ResetPasswordBody, db: Session = Depends(get_db)) -> dict[str, str]:
    try:
        validate_password(body.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    now = datetime.utcnow()
    token = db.query(OneTimeToken).filter(
        OneTimeToken.token_hash == hash_token(body.token),
        OneTimeToken.purpose == "reset_password",
        OneTimeToken.used_at.is_(None),
        OneTimeToken.expires_at > now,
    ).first()
    if not token:
        raise HTTPException(status_code=400, detail="Invalid or expired password reset token")
    user = db.query(User).filter(User.id == token.user_id, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired password reset token")
    user.password_hash = hash_password(body.new_password)
    token.used_at = now
    db.query(RefreshSession).filter(RefreshSession.user_id == user.id, RefreshSession.revoked_at.is_(None)).update(
        {"revoked_at": now}, synchronize_session=False
    )
    db.commit()
    return {"message": "Password reset. Please sign in again."}


@router.get("/me")
def me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, object]:
    return {"user": _user_payload(db, current_user)}
