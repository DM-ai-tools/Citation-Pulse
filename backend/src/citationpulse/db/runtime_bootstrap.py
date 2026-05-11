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
)


def ensure_opportunities_schema(engine: Engine) -> None:
    if engine.dialect.name != "postgresql":
        return
    try:
        with engine.begin() as conn:
            for stmt in _OPPORTUNITIES_DDL:
                conn.execute(text(stmt))
    except Exception:
        _log.exception("runtime schema bootstrap (opportunities) failed")
        raise
