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
    # --- 2026-05-14: demand resolution columns on prompts -------------------
    # Stores the precomputed demand signal (DataForSEO literal / variant /
    # internal composite / default fallback) so nightly scoring never touches
    # an external API at request time. Aligns with ``services/demand.py``.
    """
ALTER TABLE prompts
  ADD COLUMN IF NOT EXISTS demand_score numeric(5,4) NULL,
  ADD COLUMN IF NOT EXISTS demand_bucket text NULL,
  ADD COLUMN IF NOT EXISTS demand_source text NULL,
  ADD COLUMN IF NOT EXISTS demand_variant text NULL,
  ADD COLUMN IF NOT EXISTS demand_raw_volume integer NULL,
  ADD COLUMN IF NOT EXISTS demand_refreshed_at timestamptz NULL
""".strip(),
    """
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_prompts_demand_bucket') THEN
    ALTER TABLE prompts
      ADD CONSTRAINT ck_prompts_demand_bucket
      CHECK (demand_bucket IS NULL OR demand_bucket IN ('high','medium','low','unknown'));
  END IF;
END $$
""".strip(),
    """
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_prompts_demand_source') THEN
    ALTER TABLE prompts
      ADD CONSTRAINT ck_prompts_demand_source
      CHECK (demand_source IS NULL OR demand_source IN ('literal','variant','internal','default'));
  END IF;
END $$
""".strip(),
    """
CREATE INDEX IF NOT EXISTS ix_prompts_demand_refreshed_at
  ON prompts (demand_refreshed_at NULLS FIRST)
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


def ensure_opportunities_schema(engine: Engine) -> None:
    if engine.dialect.name != "postgresql":
        return
    try:
        with engine.begin() as conn:
            for stmt in _OPPORTUNITIES_DDL:
                conn.execute(text(stmt))
            for stmt in _SCAN_COMPETITOR_DDL:
                conn.execute(text(stmt))
    except Exception:
        _log.exception("runtime schema bootstrap (opportunities) failed")
        raise
