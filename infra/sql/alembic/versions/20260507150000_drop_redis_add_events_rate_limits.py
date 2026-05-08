"""scan_events + rate_limits — replace Redis with Postgres-backed pub/sub and rate-limit counters

Revision ID: 20260507150000
Revises: 20260507130000
Create Date: 2026-05-07
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260507150000"
down_revision: Union[str, None] = "20260507130000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    insp = sa.inspect(op.get_bind())
    return table_name in insp.get_table_names()


def _index_exists(table_name: str, index_name: str) -> bool:
    insp = sa.inspect(op.get_bind())
    return any(idx["name"] == index_name for idx in insp.get_indexes(table_name))


def upgrade() -> None:
    if not _table_exists("scan_events"):
        op.create_table(
            "scan_events",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True, nullable=False),
            sa.Column("scan_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("payload", postgresql.JSONB(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.ForeignKeyConstraint(["scan_id"], ["scans.id"], ondelete="CASCADE"),
        )
    if not _index_exists("scan_events", "ix_scan_events_scan_id"):
        op.create_index("ix_scan_events_scan_id", "scan_events", ["scan_id"])
    if not _index_exists("scan_events", "ix_scan_events_created_at"):
        op.create_index("ix_scan_events_created_at", "scan_events", ["created_at"])
    if not _index_exists("scan_events", "ix_scan_events_scan_id_id"):
        op.create_index(
            "ix_scan_events_scan_id_id", "scan_events", ["scan_id", "id"]
        )

    if not _table_exists("rate_limits"):
        op.create_table(
            "rate_limits",
            sa.Column("key", sa.String(length=256), primary_key=True, nullable=False),
            sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        )
    if not _index_exists("rate_limits", "ix_rate_limits_expires_at"):
        op.create_index("ix_rate_limits_expires_at", "rate_limits", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_rate_limits_expires_at", table_name="rate_limits")
    op.drop_table("rate_limits")
    op.drop_index("ix_scan_events_scan_id_id", table_name="scan_events")
    op.drop_index("ix_scan_events_created_at", table_name="scan_events")
    op.drop_index("ix_scan_events_scan_id", table_name="scan_events")
    op.drop_table("scan_events")
