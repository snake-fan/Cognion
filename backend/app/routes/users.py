import shutil
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth.dependencies import get_current_user
from ..auth.security import hash_password, validate_password, verify_password
from ..db import RefreshSession, User, UserMetadata, get_db
from ..services.config import NOTE_STORAGE_DIR, PDF_STORAGE_DIR

router = APIRouter(prefix="/users", tags=["users"])


class MetadataBody(BaseModel):
    display_name: str | None = None
    avatar_url: str | None = None
    locale: str | None = None
    timezone: str | None = None


class ChangePasswordBody(BaseModel):
    current_password: str
    new_password: str


class ConfirmPasswordBody(BaseModel):
    password: str


@router.patch("/me/metadata")
def update_metadata(
    body: MetadataBody,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    metadata = db.query(UserMetadata).filter(UserMetadata.user_id == current_user.id).first()
    if not metadata:
        raise HTTPException(status_code=404, detail="User metadata not found")
    if body.display_name is not None:
        display_name = body.display_name.strip()
        if not display_name or len(display_name) > 255:
            raise HTTPException(status_code=400, detail="Display name is required and must not exceed 255 characters")
        metadata.display_name = display_name
    if body.avatar_url is not None:
        avatar_url = body.avatar_url.strip()
        if len(avatar_url) > 2048 or (avatar_url and not avatar_url.startswith(("https://", "http://"))):
            raise HTTPException(status_code=400, detail="Avatar URL must be an HTTP(S) URL")
        metadata.avatar_url = avatar_url or None
    if body.locale is not None:
        metadata.locale = body.locale.strip()[:32] or "zh-CN"
    if body.timezone is not None:
        metadata.timezone = body.timezone.strip()[:64] or "Asia/Shanghai"
    db.commit()
    db.refresh(metadata)
    return {
        "metadata": {
            "display_name": metadata.display_name,
            "avatar_url": metadata.avatar_url,
            "locale": metadata.locale,
            "timezone": metadata.timezone,
        }
    }


@router.post("/me/change-password")
def change_password(
    body: ChangePasswordBody,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    if not verify_password(current_user.password_hash, body.current_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    try:
        validate_password(body.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    current_user.password_hash = hash_password(body.new_password)
    db.query(RefreshSession).filter(
        RefreshSession.user_id == current_user.id, RefreshSession.revoked_at.is_(None)
    ).update({"revoked_at": datetime.utcnow()}, synchronize_session=False)
    db.commit()
    return {"message": "Password changed. Please sign in again."}


@router.delete("/me")
def delete_account(
    body: ConfirmPasswordBody,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    if not verify_password(current_user.password_hash, body.password):
        raise HTTPException(status_code=400, detail="Password is incorrect")
    user_id = current_user.id
    db.delete(current_user)
    db.commit()
    storage_roots = {
        Path(__file__).resolve().parents[2] / "storage" / "users" / user_id,
        Path(PDF_STORAGE_DIR).parent / "users" / user_id,
        Path(NOTE_STORAGE_DIR).parent / "users" / user_id,
    }
    for storage_root in storage_roots:
        shutil.rmtree(storage_root, ignore_errors=True)
    return {"message": "Account permanently deleted"}
