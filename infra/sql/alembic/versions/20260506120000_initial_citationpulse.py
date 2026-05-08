"""initial citationpulse schema

Revision ID: 20260506120000
Revises:
Create Date: 2026-05-06

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from citationpulse.db.base import Base  # noqa: E402
import citationpulse.models.domain  # noqa: F401, E402

revision: str = "20260506120000"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Note: no `CREATE EXTENSION vector` — embeddings are stored as float[] so
    # the schema runs on a vanilla PostgreSQL install. If you later install
    # pgvector, you can swap citations.snippet_vec to vector(384).
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
