import base64
import hashlib
import hmac
import json
import re
import secrets
from datetime import datetime, timedelta
from uuid import uuid4

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from ..services.config import ACCESS_TOKEN_MINUTES, JWT_SECRET

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_PASSWORD_RE = re.compile(r"^[\x21-\x7e]{8,128}$")
_PASSWORD_HASHER = PasswordHasher()


class InvalidAccessToken(ValueError):
    pass


def normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if len(normalized) > 320 or not _EMAIL_RE.fullmatch(normalized):
        raise ValueError("Invalid email address")
    return normalized


def validate_password(password: str) -> None:
    if not _PASSWORD_RE.fullmatch(password):
        raise ValueError("Password must be 8-128 printable ASCII characters without spaces")


def hash_password(password: str) -> str:
    validate_password(password)
    return _PASSWORD_HASHER.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _PASSWORD_HASHER.verify(password_hash, password)
    except (InvalidHashError, VerifyMismatchError):
        return False


def new_random_token() -> str:
    return secrets.token_urlsafe(48)


def new_verification_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_verification_code(user_id: str, code: str) -> str:
    return hmac.new(JWT_SECRET.encode("utf-8"), f"{user_id}:{code}".encode("utf-8"), hashlib.sha256).hexdigest()


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_access_token(user_id: str, *, now: datetime | None = None) -> str:
    issued_at = now or datetime.utcnow()
    payload = {
        "sub": user_id,
        "iat": int(issued_at.timestamp()),
        "exp": int((issued_at + timedelta(minutes=ACCESS_TOKEN_MINUTES)).timestamp()),
        "jti": str(uuid4()),
        "type": "access",
    }
    header = {"alg": "HS256", "typ": "JWT"}
    encoded_header = _b64encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    encoded_payload = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
    signature = hmac.new(JWT_SECRET.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{encoded_header}.{encoded_payload}.{_b64encode(signature)}"


def decode_access_token(token: str, *, now: datetime | None = None) -> str:
    try:
        encoded_header, encoded_payload, encoded_signature = token.split(".")
        header = json.loads(_b64decode(encoded_header))
        payload = json.loads(_b64decode(encoded_payload))
        signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
        expected = hmac.new(JWT_SECRET.encode("utf-8"), signing_input, hashlib.sha256).digest()
        if header != {"alg": "HS256", "typ": "JWT"}:
            raise InvalidAccessToken
        if not hmac.compare_digest(expected, _b64decode(encoded_signature)):
            raise InvalidAccessToken
        current_timestamp = int((now or datetime.utcnow()).timestamp())
        if payload.get("type") != "access" or int(payload.get("exp", 0)) <= current_timestamp:
            raise InvalidAccessToken
        user_id = str(payload.get("sub") or "")
        if not user_id:
            raise InvalidAccessToken
        return user_id
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        raise InvalidAccessToken from None
