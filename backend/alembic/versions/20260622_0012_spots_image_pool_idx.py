"""idx_spots_image_pool partial index (M2, additive)

Revision ID: 0012_spots_image_pool_idx
Revises: 0011_curations
Create Date: 2026-06-22 00:00:00

Backs the quality-gate random pool for the home feed (S07 §3.3): the pool query
filters show_flag = 1 AND first_image_url IS NOT NULL, scoped by region. The
partial predicate is hand-written — autogenerate (#750/#155) drops postgresql_where.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_spots_image_pool_idx"
down_revision: str | Sequence[str] | None = "0011_curations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "idx_spots_image_pool",
        "spots",
        ["ldong_regn_cd"],
        postgresql_where=sa.text("show_flag = 1 AND first_image_url IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_spots_image_pool", table_name="spots")
