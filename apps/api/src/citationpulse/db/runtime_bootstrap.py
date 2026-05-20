"""Apply idempotent schema patches expected by the ORM (Postgres only).

Railway builds from ``apps/api`` only, so Alembic assets under ``infra/sql`` are not
in the image unless the deploy pipeline runs migrations separately. These statements
mirror ``infra/sql/20260208_opportunities_prompt_metrics.sql`` — keep them in sync.
"""

from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.engine import Engine

_log = logging.getLogger(__name__)

# One statement per execute; order matters for FK targets.
_OPPORTUNITIES_DDL: tuple[str, ...] = (
    """
ALTER TABLE prompts
  ADD COLUMN IF NOT EXISTS consecutive_gap_runs integer NOT NULL DEFAULT 0
""".strip(),
    """
CREATE TABLE IF NOT EXISTS prompt_metrics (
  prompt_id uuid PRIMARY KEY REFERENCES prompts(id) ON DELETE CASCADE,
  est_volume integer NULL,
  updated_at timestamptz NOT NULL DEFAULT now()
)
""".strip(),
    """
CREATE TABLE IF NOT EXISTS opportunities (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  brand_id uuid NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
  prompt_id uuid NOT NULL REFERENCES prompts(id) ON DELETE CASCADE,
  gap_type text NOT NULL,
  scope text NOT NULL DEFAULT '',
  grade text NOT NULL,
  opportunity_score numeric(6,4) NOT NULL,
  description text NOT NULL,
  est_volume integer NULL,
  detected_at timestamptz NOT NULL DEFAULT now(),
  status text NOT NULL DEFAULT 'open',
  CONSTRAINT ck_opportunity_grade CHECK (grade IN ('A','B','C')),
  CONSTRAINT ck_opportunity_status CHECK (status IN ('open','snoozed','queued','resolved')),
  CONSTRAINT uq_opportunity_brand_prompt_gap_scope UNIQUE (brand_id, prompt_id, gap_type, scope)
)
""".strip(),
    """
CREATE INDEX IF NOT EXISTS ix_opportunities_brand_status_score
  ON opportunities (brand_id, status, opportunity_score DESC)
""".strip(),
    """
ALTER TABLE opportunities
  ADD COLUMN IF NOT EXISTS detail_expansion text NULL
""".strip(),
)

_SCAN_COMPETITOR_DDL: tuple[str, ...] = (
    """
ALTER TABLE scans
  ADD COLUMN IF NOT EXISTS discovery_params JSONB NULL
""".strip(),
    """
ALTER TABLE scans
  ADD COLUMN IF NOT EXISTS competitor_discovery JSONB NULL
""".strip(),
)


_AUTH_DDL: tuple[str, ...] = (
    """
CREATE TABLE IF NOT EXISTS users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name varchar(256) NOT NULL,
  email varchar(320) NOT NULL,
  password_hash varchar(512) NOT NULL,
  role varchar(32) NOT NULL DEFAULT 'user',
  tenant_id uuid NULL REFERENCES tenants(id) ON DELETE SET NULL,
  is_active boolean NOT NULL DEFAULT true,
  last_login_at timestamptz NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT uq_users_email UNIQUE (email),
  CONSTRAINT ck_users_role CHECK (role IN ('user','admin'))
)
""".strip(),
    "CREATE INDEX IF NOT EXISTS ix_users_email ON users (email)",
    """
CREATE TABLE IF NOT EXISTS user_sessions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash varchar(128) NOT NULL UNIQUE,
  expires_at timestamptz NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
)
""".strip(),
    "CREATE INDEX IF NOT EXISTS ix_user_sessions_user_id ON user_sessions (user_id)",
    """
CREATE TABLE IF NOT EXISTS admin_audit_logs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  admin_user_id uuid NULL REFERENCES users(id) ON DELETE SET NULL,
  action varchar(128) NOT NULL,
  target_type varchar(64) NULL,
  target_id varchar(128) NULL,
  details jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now()
)
""".strip(),
    "CREATE INDEX IF NOT EXISTS ix_admin_audit_logs_action ON admin_audit_logs (action)",
    """
CREATE TABLE IF NOT EXISTS system_settings (
  key varchar(128) PRIMARY KEY,
  value jsonb NOT NULL DEFAULT '{}',
  updated_at timestamptz NOT NULL DEFAULT now(),
  updated_by_user_id uuid NULL REFERENCES users(id) ON DELETE SET NULL
)
""".strip(),
)


def ensure_opportunities_schema(engine: Engine) -> None:
    if engine.dialect.name != "postgresql":
        return
    try:
        with engine.begin() as conn:
            for stmt in _OPPORTUNITIES_DDL:
                conn.execute(text(stmt))
            for stmt in _SCAN_COMPETITOR_DDL:
                conn.execute(text(stmt))
            for stmt in _AUTH_DDL:
                conn.execute(text(stmt))
    except Exception:
        _log.exception("runtime schema bootstrap (opportunities) failed")


def ensure_auth_schema(engine: Engine) -> None:
    ensure_opportunities_schema(engine)
