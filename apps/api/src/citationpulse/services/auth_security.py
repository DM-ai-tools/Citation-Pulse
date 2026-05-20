"""Password hashing and JWT session tokens for native Citation Pulse auth."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import bcrypt
import jwt

from citationpulse.core.config import get_settings


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def _session_secret() -> str:
    settings = get_settings()
    secret = (settings.auth_jwt_secret or "").strip()
    if not secret:
        raise RuntimeError("AUTH_JWT_SECRET is not configured")
    return secret


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_access_token(
    *,
    user_id: UUID,
    role: str,
    email: str,
    session_id: UUID,
) -> tuple[str, datetime]:
    settings = get_settings()
    expires = datetime.now(timezone.utc) + timedelta(hours=settings.auth_jwt_expire_hours)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "email": email,
        "sid": str(session_id),
        "type": "access",
        "exp": expires,
        "iat": datetime.now(timezone.utc),
    }
    token = jwt.encode(payload, _session_secret(), algorithm="HS256")
    return token, expires


def decode_access_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, _session_secret(), algorithms=["HS256"])


def new_session_token() -> str:
    return secrets.token_urlsafe(48)


def password_strength_errors(password: str) -> list[str]:
    issues: list[str] = []
    if len(password) < 8:
        issues.append("At least 8 characters")
    if not any(c.isupper() for c in password):
        issues.append("One uppercase letter")
    if not any(c.islower() for c in password):
        issues.append("One lowercase letter")
    if not any(c.isdigit() for c in password):
        issues.append("One number")
    return issues
