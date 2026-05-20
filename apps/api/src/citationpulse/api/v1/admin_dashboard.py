"""Admin dashboard API — separate from user auth; requires admin role."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, or_, select

from citationpulse.api.deps import AdminUser, DbSession
from citationpulse.models.domain import Brand, Scan, SystemSetting, User, UserRole
from citationpulse.services.auth_service import write_audit_log

from citationpulse.api.deps import get_auth_context

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(get_auth_context)],
)


class AdminStats(BaseModel):
    total_users: int
    active_users: int
    total_scans: int
    completed_scans: int
    total_brands: int


class AdminUserRow(BaseModel):
    id: UUID
    name: str
    email: EmailStr
    role: str
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None


class AdminScanRow(BaseModel):
    id: UUID
    status: str
    submitted_url: str
    brand_id: UUID | None
    created_at: datetime | None
    completed_at: datetime | None


class AuditLogRow(BaseModel):
    id: UUID
    action: str
    target_type: str | None
    target_id: str | None
    details: dict[str, Any]
    created_at: datetime


@router.get("/stats", response_model=AdminStats)
def admin_stats(db: DbSession, _admin: AdminUser) -> AdminStats:
    total_users = db.scalar(select(func.count()).select_from(User)) or 0
    active_users = (
        db.scalar(select(func.count()).select_from(User).where(User.is_active.is_(True))) or 0
    )
    total_scans = db.scalar(select(func.count()).select_from(Scan)) or 0
    completed_scans = (
        db.scalar(select(func.count()).select_from(Scan).where(Scan.status == "completed")) or 0
    )
    total_brands = db.scalar(select(func.count()).select_from(Brand)) or 0
    return AdminStats(
        total_users=total_users,
        active_users=active_users,
        total_scans=total_scans,
        completed_scans=completed_scans,
        total_brands=total_brands,
    )


@router.get("/users", response_model=list[AdminUserRow])
def list_users(db: DbSession, _admin: AdminUser, q: str | None = None) -> list[AdminUserRow]:
    stmt = select(User).order_by(User.created_at.desc()).limit(200)
    if q and q.strip():
        like = f"%{q.strip().lower()}%"
        stmt = stmt.where(
            func.lower(User.email).like(like) | func.lower(User.name).like(like)
        )
    rows = list(db.scalars(stmt).all())
    return [
        AdminUserRow(
            id=u.id,
            name=u.name,
            email=u.email,
            role=u.role,
            is_active=u.is_active,
            created_at=u.created_at,
            last_login_at=u.last_login_at,
        )
        for u in rows
    ]


class RoleUpdate(BaseModel):
    role: str = Field(..., pattern="^(user|admin)$")


class AdminUserScansResponse(BaseModel):
    user: AdminUserRow
    scans: list[AdminScanRow]


@router.get("/users/{user_id}/scans", response_model=AdminUserScansResponse)
def list_user_scans(user_id: UUID, db: DbSession, _admin: AdminUser) -> AdminUserScansResponse:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    scans: list[Scan] = []
    if user.tenant_id:
        brand_ids = select(Brand.id).where(Brand.tenant_id == user.tenant_id)
        scans = list(
            db.scalars(
                select(Scan)
                .where(or_(Scan.tenant_id == user.tenant_id, Scan.brand_id.in_(brand_ids)))
                .order_by(Scan.created_at.desc())
                .limit(500)
            ).all()
        )

    return AdminUserScansResponse(
        user=AdminUserRow(
            id=user.id,
            name=user.name,
            email=user.email,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
            last_login_at=user.last_login_at,
        ),
        scans=[
            AdminScanRow(
                id=s.id,
                status=s.status,
                submitted_url=s.submitted_url,
                brand_id=s.brand_id,
                created_at=s.created_at,
                completed_at=s.completed_at,
            )
            for s in scans
        ],
    )


@router.patch("/users/{user_id}/role", response_model=AdminUserRow)
def update_user_role(
    user_id: UUID,
    body: RoleUpdate,
    db: DbSession,
    admin: AdminUser,
) -> AdminUserRow:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    old = user.role
    user.role = body.role
    user.updated_at = datetime.now(timezone.utc)
    write_audit_log(
        db,
        admin_user_id=admin.id,
        action="user.role_change",
        target_type="user",
        target_id=str(user_id),
        details={"from": old, "to": body.role},
    )
    db.commit()
    db.refresh(user)
    return AdminUserRow(
        id=user.id,
        name=user.name,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


@router.get("/scans", response_model=list[AdminScanRow])
def list_scans(db: DbSession, _admin: AdminUser, limit: int = 100) -> list[AdminScanRow]:
    rows = list(db.scalars(select(Scan).order_by(Scan.created_at.desc()).limit(min(limit, 500))).all())
    return [
        AdminScanRow(
            id=s.id,
            status=s.status,
            submitted_url=s.submitted_url,
            brand_id=s.brand_id,
            created_at=s.created_at,
            completed_at=s.completed_at,
        )
        for s in rows
    ]


@router.delete("/scans/{scan_id}")
def delete_scan(scan_id: UUID, db: DbSession, admin: AdminUser) -> dict[str, str]:
    scan = db.get(Scan, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    db.delete(scan)
    write_audit_log(
        db,
        admin_user_id=admin.id,
        action="scan.delete",
        target_type="scan",
        target_id=str(scan_id),
    )
    db.commit()
    return {"status": "deleted"}


@router.get("/audit-logs", response_model=list[AuditLogRow])
def audit_logs(db: DbSession, _admin: AdminUser, limit: int = 100) -> list[AuditLogRow]:
    from citationpulse.models.domain import AdminAuditLog

    rows = list(
        db.scalars(
            select(AdminAuditLog).order_by(AdminAuditLog.created_at.desc()).limit(min(limit, 500))
        ).all()
    )
    return [
        AuditLogRow(
            id=r.id,
            action=r.action,
            target_type=r.target_type,
            target_id=r.target_id,
            details=r.details or {},
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.get("/settings")
def get_settings(db: DbSession, _admin: AdminUser) -> dict[str, Any]:
    rows = list(db.scalars(select(SystemSetting)).all())
    return {r.key: r.value for r in rows}


class SettingUpdate(BaseModel):
    value: dict[str, Any]


@router.put("/settings/{key}")
def put_setting(
    key: str,
    body: SettingUpdate,
    db: DbSession,
    admin: AdminUser,
) -> dict[str, str]:
    row = db.get(SystemSetting, key)
    if not row:
        row = SystemSetting(key=key, value=body.value, updated_by_user_id=admin.id)
        db.add(row)
    else:
        row.value = body.value
        row.updated_by_user_id = admin.id
    write_audit_log(
        db,
        admin_user_id=admin.id,
        action="settings.update",
        target_type="setting",
        target_id=key,
        details=body.value,
    )
    db.commit()
    return {"status": "ok"}
