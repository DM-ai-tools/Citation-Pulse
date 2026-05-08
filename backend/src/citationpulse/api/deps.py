from __future__ import annotations

import logging
from typing import Annotated, Any
from uuid import UUID

import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from citationpulse.core.config import get_settings
from citationpulse.db.session import get_db
from citationpulse.models.domain import Membership, Tenant

_log = logging.getLogger(__name__)
bearer_scheme = HTTPBearer(auto_error=False)


def decode_clerk_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    if not settings.clerk_jwks_url:
        raise jwt.InvalidTokenError("Clerk JWKS not configured")
    import httpx
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


def get_auth_context(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    x_api_key: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    settings = get_settings()
    if settings.internal_api_key and x_api_key == settings.internal_api_key:
        return {"mode": "api_key", "sub": None, "org_id": None}

    if settings.internal_phase1 and settings.environment == "development" and not settings.clerk_jwks_url:
        if creds is None:
            return {"mode": "dev", "sub": "dev-user", "org_id": None}
        try:
            return {"mode": "clerk", **decode_clerk_token(creds.credentials)}
        except jwt.PyJWTError:
            return {"mode": "dev", "sub": "dev-user", "org_id": None}

    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        return {"mode": "clerk", **decode_clerk_token(creds.credentials)}
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e)) from e


def resolve_tenant(db: Session, claims: dict[str, Any]) -> Tenant:
    org_id = claims.get("org_id") or claims.get("organization_id")
    if org_id:
        tenant = db.query(Tenant).filter(Tenant.clerk_org_id == org_id).one_or_none()
        if not tenant:
            tenant = Tenant(name=f"org-{org_id}", clerk_org_id=org_id, plan="saas")
            db.add(tenant)
            db.flush()
            sub = claims.get("sub")
            if sub:
                db.add(Membership(tenant_id=tenant.id, clerk_user_id=sub, role="owner"))
            db.commit()
            db.refresh(tenant)
        return tenant

    # Phase 1 / dev: single default tenant
    tenant = db.query(Tenant).order_by(Tenant.created_at.asc()).first()
    if not tenant:
        tenant = Tenant(name="Default", plan="saas")
        db.add(tenant)
        db.commit()
        db.refresh(tenant)
    return tenant


def require_tenant_id(tenant: Tenant) -> UUID:
    return tenant.id


DbSession = Annotated[Session, Depends(get_db)]
AuthContext = Annotated[dict[str, Any], Depends(get_auth_context)]


def get_current_tenant(db: DbSession, ctx: AuthContext) -> Tenant:
    return resolve_tenant(db, ctx)


CurrentTenant = Annotated[Tenant, Depends(get_current_tenant)]
