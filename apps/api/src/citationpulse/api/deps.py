from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Annotated, Any
from uuid import UUID

import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from citationpulse.core.config import get_settings
from citationpulse.db.session import get_db
from citationpulse.models.domain import Membership, Tenant, User, UserRole, UserSession
from citationpulse.services.auth_security import decode_access_token, hash_session_token

_log = logging.getLogger(__name__)
bearer_scheme = HTTPBearer(auto_error=False)


def decode_clerk_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    if not settings.clerk_jwks_url:
        raise jwt.InvalidTokenError("Clerk JWKS not configured")
    from jwt import PyJWKClient

    jwks_client = PyJWKClient(settings.clerk_jwks_url)
    signing_key = jwks_client.get_signing_key_from_jwt(token)
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        audience=settings.clerk_audience or None,
        issuer=settings.clerk_issuer or None,
    )


def _authenticate_local_bearer(db: Session, token: str) -> dict[str, Any] | None:
    settings = get_settings()
    if not (settings.auth_jwt_secret or "").strip():
        return None
    try:
        claims = decode_access_token(token)
    except jwt.PyJWTError:
        return None
    if claims.get("type") != "access":
        return None
    token_hash = hash_session_token(token)
    session = db.query(UserSession).filter(UserSession.token_hash == token_hash).one_or_none()
    if not session or session.expires_at < datetime.now(timezone.utc):
        return None
    user = db.get(User, UUID(str(claims["sub"])))
    if not user or not user.is_active:
        return None
    return {
        "mode": "local",
        "sub": str(user.id),
        "user_id": user.id,
        "role": user.role,
        "email": user.email,
        "org_id": str(user.tenant_id) if user.tenant_id else None,
    }


def get_auth_context(
    db: DbSession,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    x_api_key: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    settings = get_settings()
    if settings.internal_api_key and x_api_key == settings.internal_api_key:
        return {"mode": "api_key", "sub": None, "org_id": None}

    if creds and creds.scheme.lower() == "bearer":
        local = _authenticate_local_bearer(db, creds.credentials)
        if local:
            return local

    dev_bypass = (
        settings.internal_phase1
        and settings.environment == "development"
        and not settings.clerk_jwks_url
        and not (settings.auth_jwt_secret or "").strip()
    )
    if dev_bypass:
        if creds is None:
            return {"mode": "dev", "sub": "dev-user", "org_id": None}
        try:
            return {"mode": "clerk", **decode_clerk_token(creds.credentials)}
        except jwt.PyJWTError:
            return {"mode": "dev", "sub": "dev-user", "org_id": None}

    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    if settings.clerk_jwks_url:
        try:
            return {"mode": "clerk", **decode_clerk_token(creds.credentials)}
        except jwt.PyJWTError as e:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e)) from e

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")


def resolve_tenant(db: Session, claims: dict[str, Any]) -> Tenant:
    if claims.get("mode") == "local":
        user_id = claims.get("user_id")
        if user_id:
            user = db.get(User, user_id) if isinstance(user_id, UUID) else db.get(User, UUID(str(user_id)))
            if user and user.tenant_id:
                tenant = db.get(Tenant, user.tenant_id)
                if tenant:
                    return tenant

    org_id = claims.get("org_id") or claims.get("organization_id")
    if org_id and claims.get("mode") == "clerk":
        tenant = db.query(Tenant).filter(Tenant.clerk_org_id == org_id).one_or_none()
        if not tenant:
            tenant = Tenant(name=f"org-{org_id}", clerk_org_id=org_id, plan="saas")
            db.add(tenant)
            db.flush()
            sub = claims.get("sub")
            if sub:
                db.add(Membership(tenant_id=tenant.id, clerk_user_id=str(sub), role="owner"))
            db.commit()
            db.refresh(tenant)
        return tenant

    tenant = db.query(Tenant).order_by(Tenant.created_at.asc()).first()
    if not tenant:
        tenant = Tenant(name="Default", plan="saas")
        db.add(tenant)
        db.commit()
        db.refresh(tenant)
    return tenant


def get_current_user(
    db: DbSession,
    ctx: AuthContext,
) -> User:
    if ctx.get("mode") != "local":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User session required")
    user = db.get(User, UUID(str(ctx["sub"])))
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def require_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.role != UserRole.ADMIN.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


DbSession = Annotated[Session, Depends(get_db)]
AuthContext = Annotated[dict[str, Any], Depends(get_auth_context)]
CurrentUser = Annotated[User, Depends(get_current_user)]
AdminUser = Annotated[User, Depends(require_admin)]


def get_current_tenant(db: DbSession, ctx: AuthContext) -> Tenant:
    return resolve_tenant(db, ctx)


CurrentTenant = Annotated[Tenant, Depends(get_current_tenant)]
