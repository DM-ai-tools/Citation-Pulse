"""scans table + engine_runs.scan_id

Revision ID: 20260507130000
Revises: 20260506120000
Create Date: 2026-05-07

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260507130000"
down_revision: Union[str, None] = "20260506120000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    insp = sa.inspect(op.get_bind())
    return table_name in insp.get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    insp = sa.inspect(op.get_bind())
    return any(col["name"] == column_name for col in insp.get_columns(table_name))


def _index_exists(table_name: str, index_name: str) -> bool:
    insp = sa.inspect(op.get_bind())
    return any(idx["name"] == index_name for idx in insp.get_indexes(table_name))


def _foreign_key_exists(table_name: str, fk_name: str) -> bool:
    insp = sa.inspect(op.get_bind())
    return any(fk.get("name") == fk_name for fk in insp.get_foreign_keys(table_name))


def upgrade() -> None:
    if not _table_exists("scans"):
        op.create_table(
            "scans",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("brand_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("submitted_url", sa.Text(), nullable=False),
            sa.Column("locale", sa.String(length=32), nullable=False, server_default="en-US"),
            sa.Column(
                "engines",
                postgresql.ARRAY(sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::text[]"),
            ),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
            sa.Column("score_overall", sa.Integer(), nullable=True),
            sa.Column("share_token", sa.String(length=128), nullable=True),
            sa.Column("share_public", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["brand_id"], ["brands.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="SET NULL"),
        )

    if not _index_exists("scans", "ix_scans_tenant_id"):
        op.create_index("ix_scans_tenant_id", "scans", ["tenant_id"])
    if not _index_exists("scans", "ix_scans_brand_id"):
        op.create_index("ix_scans_brand_id", "scans", ["brand_id"])
    if not _index_exists("scans", "ix_scans_status"):
        op.create_index("ix_scans_status", "scans", ["status"])
    if not _index_exists("scans", "ix_scans_share_token"):
        op.create_index("ix_scans_share_token", "scans", ["share_token"], unique=True)

    if not _column_exists("engine_runs", "scan_id"):
        op.add_column(
            "engine_runs",
            sa.Column("scan_id", postgresql.UUID(as_uuid=True), nullable=True),
        )
    if not _foreign_key_exists("engine_runs", "fk_engine_runs_scan_id_scans"):
        op.create_foreign_key(
            "fk_engine_runs_scan_id_scans",
            "engine_runs",
            "scans",
            ["scan_id"],
            ["id"],
            ondelete="SET NULL",
        )
    if not _index_exists("engine_runs", "ix_engine_runs_scan_id"):
        op.create_index("ix_engine_runs_scan_id", "engine_runs", ["scan_id"])


def downgrade() -> None:
    op.drop_index("ix_engine_runs_scan_id", table_name="engine_runs")
    op.drop_constraint("fk_engine_runs_scan_id_scans", "engine_runs", type_="foreignkey")
    op.drop_column("engine_runs", "scan_id")
    op.drop_index("ix_scans_share_token", table_name="scans")
    op.drop_index("ix_scans_status", table_name="scans")
    op.drop_index("ix_scans_brand_id", table_name="scans")
    op.drop_index("ix_scans_tenant_id", table_name="scans")
    op.drop_table("scans")
