from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from citationpulse.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PlanType(str, enum.Enum):
    SAAS = "saas"
    DFY = "dfy"


class EngineType(str, enum.Enum):
    CHATGPT = "chatgpt"
    PERPLEXITY = "perplexity"
    GOOGLE_AIO = "google_aio"
    GEMINI = "gemini"
    CLAUDE = "claude"


# --- Engine feature flags ---------------------------------------------------
# Deprecated: retained only for backward compatibility with existing imports.
GOOGLE_AIO_ENABLED: bool = False


def default_engines() -> list[str]:
    """Engines included when the caller doesn't pass an explicit `engines` list.

    Single source of truth: API request defaults, fan-out tasks, snapshot
    fall-backs, and canary checks all funnel through here so we can add or
    remove engines in one place.
    """
    return [
        EngineType.CHATGPT.value,
        EngineType.CLAUDE.value,
        EngineType.GEMINI.value,
        EngineType.PERPLEXITY.value,
    ]


def all_engines() -> list[str]:
    """Every engine value, regardless of whether it's enabled by default."""
    return [e.value for e in EngineType]


class RunStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    OK = "ok"
    ERROR = "error"


class Ownership(str, enum.Enum):
    BRAND = "brand"
    COMPETITOR = "competitor"
    THIRD_PARTY = "third_party"
    NEUTRAL = "neutral"


class Sentiment(str, enum.Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class AlertChannel(str, enum.Enum):
    EMAIL = "email"
    SLACK = "slack"


class Tenant(Base):
    __tablename__ = "tenants"
    __table_args__ = (CheckConstraint("plan IN ('saas','dfy')", name="ck_tenants_plan"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    plan: Mapped[str] = mapped_column(String(32), nullable=False, default=PlanType.SAAS.value)
    clerk_org_id: Mapped[str | None] = mapped_column(String(128), unique=True, index=True)
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(128), index=True)
    monthly_cost_cap_usd: Mapped[Any | None] = mapped_column(Numeric(12, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    memberships: Mapped[list[Membership]] = relationship(back_populates="tenant")
    brands: Mapped[list[Brand]] = relationship(back_populates="tenant")


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("tenant_id", "clerk_user_id", name="uq_membership_tenant_user"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    clerk_user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(64), nullable=False, default="member")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    tenant: Mapped[Tenant] = relationship(back_populates="memberships")


class Brand(Base):
    __tablename__ = "brands"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    domains: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'")
    )
    competitors: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False, server_default=text("'{}'::uuid[]")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    tenant: Mapped[Tenant] = relationship(back_populates="brands")
    prompts: Mapped[list[Prompt]] = relationship(back_populates="brand")
    scans: Mapped[list["Scan"]] = relationship(back_populates="brand")


class Scan(Base):
    """One-shot funnel scan (landing → live → report)."""

    __tablename__ = "scans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True, index=True
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("brands.id", ondelete="CASCADE"), nullable=False, index=True
    )
    submitted_url: Mapped[str] = mapped_column(Text, nullable=False)
    locale: Mapped[str] = mapped_column(String(32), nullable=False, default="en-US")
    engines: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default=text("'{}'::text[]"))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued", index=True)
    score_overall: Mapped[int | None] = mapped_column(Integer)
    share_token: Mapped[str | None] = mapped_column(String(128), unique=True, index=True)
    share_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    brand: Mapped[Brand] = relationship(back_populates="scans")
    engine_runs: Mapped[list["EngineRun"]] = relationship(back_populates="scan")


class Prompt(Base):
    __tablename__ = "prompts"
    __table_args__ = (UniqueConstraint("brand_id", "text", "locale", name="uq_prompt_brand_text_locale"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    brand_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("brands.id", ondelete="CASCADE"), nullable=False, index=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    locale: Mapped[str] = mapped_column(String(32), nullable=False, default="en-US")
    intent: Mapped[str | None] = mapped_column(String(128))
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    brand: Mapped[Brand] = relationship(back_populates="prompts")
    engine_runs: Mapped[list[EngineRun]] = relationship(back_populates="prompt")


class EngineRun(Base):
    __tablename__ = "engine_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    prompt_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("prompts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    engine: Mapped[EngineType] = mapped_column(Enum(EngineType, name="engine_type"), nullable=False, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=RunStatus.QUEUED.value, index=True)
    raw_ref: Mapped[str | None] = mapped_column(String(2048))
    cost_usd: Mapped[Any | None] = mapped_column(Numeric(10, 4))
    error_message: Mapped[str | None] = mapped_column(Text)
    scan_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("scans.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    prompt: Mapped[Prompt] = relationship(back_populates="engine_runs")
    scan: Mapped["Scan | None"] = relationship(back_populates="engine_runs")
    citations: Mapped[list[Citation]] = relationship(back_populates="engine_run")


class Citation(Base):
    __tablename__ = "citations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    engine_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("engine_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    position: Mapped[int | None] = mapped_column(Integer)
    snippet: Mapped[str | None] = mapped_column(Text)
    # Embedding vector for semantic citation matching. Stored as float[] so we
    # don't require the Postgres `vector` extension. When/if pgvector is
    # available later, this can be migrated to vector(384) without code changes.
    snippet_vec: Mapped[list[float] | None] = mapped_column(ARRAY(Float))
    ownership: Mapped[str] = mapped_column(String(32), nullable=False, default=Ownership.NEUTRAL.value)
    sentiment: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    engine_run: Mapped[EngineRun] = relationship(back_populates="citations")


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    brand_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("brands.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rule: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    fired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)


class AlertRule(Base):
    """Configurable alert rules (dedupe in application layer)."""

    __tablename__ = "alert_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    brand_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("brands.id", ondelete="CASCADE"), index=True)
    rule: Mapped[str] = mapped_column(String(128), nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    channel: Mapped[str] = mapped_column(String(32), nullable=False, default=AlertChannel.SLACK.value)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class CampaignTask(Base):
    """DFY: citation-build campaign queue."""

    __tablename__ = "campaign_tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("brands.id", ondelete="CASCADE"), nullable=False, index=True
    )
    prompt_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("prompts.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="queued")
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class CommsLog(Base):
    """DFY: client communications log."""

    __tablename__ = "comms_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("brands.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entry: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class WebhookSubscription(Base):
    """Partner webhooks (Phase 3)."""

    __tablename__ = "webhook_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    secret: Mapped[str] = mapped_column(String(256), nullable=False)
    events: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class ScanEvent(Base):
    """Live scan-progress events. Replaces Redis pub/sub: workers append rows,
    the SSE endpoint long-polls for `id > last_seen`."""

    __tablename__ = "scan_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    scan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, index=True
    )


class RateLimit(Base):
    """Token-bucket counters keyed by hour. Replaces Redis INCR/EXPIRE.

    `key` examples:
      rl:anon_scan:<ip>:<hour_epoch>
      rl:brand_run:<brand_uuid>:<hour_epoch>
    """

    __tablename__ = "rate_limits"

    key: Mapped[str] = mapped_column(String(256), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
