"""prompts.consecutive_gap_runs + prompt_metrics + opportunities (Top Gap Opportunities)

Revision ID: 20260511100000
Revises: 20260507150000
Create Date: 2026-05-11
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260511100000"
down_revision: Union[str, None] = "20260507150000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "ALTER TABLE prompts ADD COLUMN IF NOT EXISTS "
            "consecutive_gap_runs integer NOT NULL DEFAULT 0"
        )
    )
    op.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS prompt_metrics (
              prompt_id uuid PRIMARY KEY REFERENCES prompts(id) ON DELETE CASCADE,
              est_volume integer NULL,
              updated_at timestamptz NOT NULL DEFAULT now()
            )
            """
        )
    )
    op.execute(
        sa.text(
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
            """
        )
    )
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_opportunities_brand_status_score "
            "ON opportunities (brand_id, status, opportunity_score DESC)"
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS ix_opportunities_brand_status_score"))
    op.execute(sa.text("DROP TABLE IF EXISTS opportunities"))
    op.execute(sa.text("DROP TABLE IF EXISTS prompt_metrics"))
    op.execute(sa.text("ALTER TABLE prompts DROP COLUMN IF EXISTS consecutive_gap_runs"))
