"""SPT: spot_concentration (KTO 관광지 집중률 / TatsCnctrRateService)

Revision ID: 0009_spt_concentration
Revises: 0008_spt_search_trgm
Create Date: 2026-06-06 00:00:00

Backs ``GET /v1/spots/trending`` (#2 전국 "집중률 TOP", ADR-0016). Stores the
㈜KT mobile-data forward-30-day visitor concentration from KTO
TatsCnctrRateService (data.go.kr 15128555), name-matched to our active spots.
One row per spot (the collection-day value). The ``concentration_rate DESC``
index backs the nationwide ranking read. Populated by the manual
``scripts/sync_concentration.py`` run, not a worker.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_spt_concentration"
down_revision: str | Sequence[str] | None = "0008_spt_search_trgm"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "spot_concentration",
        sa.Column("content_id", sa.String(length=32), nullable=False),
        sa.Column("concentration_rate", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("base_ymd", sa.Date(), nullable=False),
        sa.Column("raw_name", sa.String(length=255), nullable=False),
        sa.Column("signgu_cd", sa.String(length=8), nullable=True),
        sa.Column(
            "collected_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "concentration_rate >= 0 AND concentration_rate <= 100",
            name="ck_spot_concentration_rate_range",
        ),
        sa.ForeignKeyConstraint(["content_id"], ["spots.content_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("content_id"),
    )
    op.execute(
        "CREATE INDEX idx_spot_concentration_rate ON spot_concentration (concentration_rate DESC)"
    )


def downgrade() -> None:
    op.drop_index("idx_spot_concentration_rate", table_name="spot_concentration")
    op.drop_table("spot_concentration")
