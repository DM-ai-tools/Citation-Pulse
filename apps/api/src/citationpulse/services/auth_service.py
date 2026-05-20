"""Signup, login, sessions, and admin audit for native auth."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from citationpulse.models.domain import (
    AdminAuditLog,
    Membership,
    Tenant,
    User,
    UserRole,
    UserSession,
)
from citationpulse.schemas.auth import AuthResponse, UserPublic
from citationpulse.services.auth_security import (
    create_access_token,
    hash_password,
    hash_session_token,
    new_session_token,
    password_strength_errors,
    verify_password,
)

_log = logging.getLogger(__name__)


def _user_public(user: User) -> UserPublic:
    return UserPublic(
        id=user.id,
        name=user.name,
        email=user.email,
        role=user.role,
        tenant_id=user.tenant_id,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
    )


def _issue_session(db: Session, user: User, *, remember: bool = False) -> AuthResponse:
    _ = remember
    session = UserSession(
        user_id=user.id,
        token_hash="pending",
        expires_at=datetime.now(timezone.utc),
    )
    db.add(session)
    db.flush()
    access_token, expires = create_access_token(
        user_id=user.id,
        role=user.role,
        email=user.email,
        session_id=session.id,
    )
    session.token_hash = hash_session_token(access_token)
    session.expires_at = expires
    user.last_login_at = datetime.now(timezone.utc)
    db.flush()
    return AuthResponse(
        access_token=access_token,
        expires_at=expires,
        user=_user_public(user),
    )


def signup_user(db: Session, *, name: str, email: str, password: str) -> AuthResponse:
    email_norm = email.strip().lower()
    issues = password_strength_errors(password)
    if issues:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Password too weak", "issues": issues},
        )

    existing = db.scalar(select(User).where(User.email == email_norm))
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    tenant = Tenant(name=f"{name.strip()}'s workspace", plan="saas")
    db.add(tenant)
    db.flush()

    user = User(
        name=name.strip(),
        email=email_norm,
        password_hash=hash_password(password),
        role=UserRole.USER.value,
        tenant_id=tenant.id,
    )
    db.add(user)
    db.flush()

    db.add(
        Membership(
            tenant_id=tenant.id,
            clerk_user_id=f"local:{user.id}",
            role="owner",
        )
    )
    db.refresh(user)
    resp = _issue_session(db, user)
    db.commit()
    return resp


def find_user_by_login_identifier(db: Session, identifier: str) -> User | None:
    """Match email (contains @) or display name (case-insensitive), e.g. Traffic-Radius."""
    raw = identifier.strip()
    if not raw:
        return None
    if "@" in raw:
        return db.scalar(select(User).where(User.email == raw.lower()))
    return db.scalar(select(User).where(func.lower(User.name) == raw.lower()))


def login_user(
    db: Session,
    *,
    email: str,
    password: str,
    remember: bool = False,
    admin_only: bool = False,
    identifier: str | None = None,
) -> AuthResponse:
    login_id = (identifier or email).strip()
    user = find_user_by_login_identifier(db, login_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if not verify_password(password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if admin_only and user.role != UserRole.ADMIN.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    if not admin_only and user.role == UserRole.ADMIN.value:
        pass  # admins may use user login too
    db.refresh(user)
    resp = _issue_session(db, user, remember=remember)
    db.commit()
    if admin_only:
        write_audit_log(
            db,
            admin_user_id=user.id,
            action="admin.login",
            target_type="user",
            target_id=str(user.id),
        )
        db.commit()
    return resp


def logout_token(db: Session, token_hash: str) -> None:
    session = db.scalar(select(UserSession).where(UserSession.token_hash == token_hash))
    if session:
        db.delete(session)
        db.commit()


def get_user_by_id(db: Session, user_id: UUID) -> User | None:
    return db.get(User, user_id)


def write_audit_log(
    db: Session,
    *,
    admin_user_id: UUID | None,
    action: str,
    target_type: str | None = None,
    target_id: str | None = None,
    details: dict | None = None,
) -> None:
    db.add(
        AdminAuditLog(
            admin_user_id=admin_user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=details or {},
        )
    )
    db.flush()


def ensure_default_admin(db: Session) -> None:
    """Create or sync admin account from AUTH_ADMIN_* env vars."""
    from citationpulse.core.config import get_settings

    settings = get_settings()
    email = (settings.auth_admin_email or "").strip().lower()
    password = settings.auth_admin_password or ""
    name = (settings.auth_admin_name or "Administrator").strip() or "Administrator"
    if not email or not password:
        return

    pw_hash = hash_password(password)
    by_email = db.scalar(select(User).where(User.email == email))
    if by_email:
        by_email.name = name
        by_email.password_hash = pw_hash
        by_email.role = UserRole.ADMIN.value
        by_email.is_active = True
        db.commit()
        _log.info("Synced admin user %s (%s)", name, email)
        return

    by_name = db.scalar(select(User).where(func.lower(User.name) == name.lower()))
    if by_name:
        by_name.email = email
        by_name.password_hash = pw_hash
        by_name.role = UserRole.ADMIN.value
        by_name.is_active = True
        db.commit()
        _log.info("Synced admin user %s → %s", name, email)
        return

    existing_admin = db.scalar(select(User).where(User.role == UserRole.ADMIN.value).limit(1))
    if existing_admin:
        existing_admin.name = name
        existing_admin.email = email
        existing_admin.password_hash = pw_hash
        db.commit()
        _log.info("Updated existing admin to %s (%s)", name, email)
        return

    db.add(
        User(
            name=name,
            email=email,
            password_hash=pw_hash,
            role=UserRole.ADMIN.value,
            tenant_id=None,
        )
    )
    db.commit()
    _log.info("Seeded admin user %s (%s)", name, email)
