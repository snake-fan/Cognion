from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from ..db import User, get_db
from .context import set_current_user_id
from .security import InvalidAccessToken, decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Authentication required", headers={"WWW-Authenticate": "Bearer"})
    try:
        user_id = decode_access_token(credentials.credentials)
    except InvalidAccessToken:
        raise HTTPException(status_code=401, detail="Invalid or expired access token") from None
    user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
    if not user or user.email_verified_at is None:
        raise HTTPException(status_code=401, detail="Invalid or expired access token")
    db.info["user_id"] = user.id
    set_current_user_id(user.id)
    return user
