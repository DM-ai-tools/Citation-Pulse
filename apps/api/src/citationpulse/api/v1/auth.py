"""Native email/password authentication (separate from Clerk)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import HTTPAuthorizationCredentials

from citationpulse.api.deps import CurrentUser, DbSession, bearer_scheme
from citationpulse.schemas.auth import (
    AdminLoginRequest,
    AuthResponse,
    LoginRequest,
    MessageResponse,
    SignupRequest,
    UserPublic,
)
from citationpulse.services.auth_security import decode_access_token, hash_session_token
from citationpulse.services.auth_service import (
    login_user,
    logout_token,
    signup_user,
    write_audit_log,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def signup(body: SignupRequest, db: DbSession) -> AuthResponse:
    return signup_user(db, name=body.name, email=str(body.email), password=body.password)


@router.post("/login", response_model=AuthResponse)
def login(body: LoginRequest, db: DbSession) -> AuthResponse:
    return login_user(
        db,
        email=str(body.email),
        password=body.password,
        remember=body.remember,
        admin_only=False,
    )


@router.post("/admin/login", response_model=AuthResponse)
def admin_login(body: AdminLoginRequest, db: DbSession) -> AuthResponse:
    return login_user(
        db,
        email=str(body.username),
        password=body.password,
        remember=True,
        admin_only=True,
        identifier=body.username,
    )


@router.post("/logout", response_model=MessageResponse)
def logout(
    db: DbSession,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> MessageResponse:
    if creds and creds.scheme.lower() == "bearer":
        logout_token(db, hash_session_token(creds.credentials))
    return MessageResponse(message="Logged out")


@router.get("/me", response_model=UserPublic)
def me(user: CurrentUser) -> UserPublic:
    from citationpulse.services.auth_service import _user_public

    return _user_public(user)
