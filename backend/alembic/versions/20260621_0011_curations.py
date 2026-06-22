"""curations + curation_spots (M1, additive)

Revision ID: 0011_curations
Revises: 0010_drop_dead_tables
Create Date: 2026-06-21 00:00:00

First-class curation entity backing the home feed (hero 6 + mood rails 3) and the
region/mood detail pages (S07 §3.1/§3.2). Additive only — this is the rollback
target for the expand→contract refactor; destructive drops land later (M3/M4).

Named CHECK constraints (ck_curation_type/ck_curation_scope) and FK ondelete
clauses are hand-authored — autogenerate cannot track anonymous constraints.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_curations"
down_revision: str | Sequence[str] | None = "0010_drop_dead_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "curations",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("type", sa.String(16), nullable=False),
        sa.Column("slug", sa.String(80), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("subtitle", sa.Text(), nullable=True),
        sa.Column("lead", sa.Text(), nullable=True),
        sa.Column("intro", sa.Text(), nullable=True),
        sa.Column("cover_spot_id", sa.String(32), nullable=True),
        sa.Column("region_cd", sa.String(8), nullable=True),
        sa.Column("mood_id", sa.SmallInteger(), nullable=True),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["cover_spot_id"], ["spots.content_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["region_cd"], ["regions.ldong_regn_cd"]),
        sa.ForeignKeyConstraint(["mood_id"], ["moods.id"]),
        sa.CheckConstraint("type IN ('region','mood','editorial')", name="ck_curation_type"),
        sa.CheckConstraint(
            "(type='region' AND region_cd IS NOT NULL) "
            "OR (type='mood' AND mood_id IS NOT NULL) "
            "OR type='editorial'",
            name="ck_curation_scope",
        ),
        sa.UniqueConstraint("slug", name="uq_curations_slug"),
    )
    op.create_index("idx_curations_feed", "curations", ["type", "is_published", "position"])

    op.create_table(
        "curation_spots",
        sa.Column("curation_id", sa.BigInteger(), nullable=False),
        sa.Column("content_id", sa.String(32), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["curation_id"], ["curations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["content_id"], ["spots.content_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("curation_id", "content_id"),
    )
    op.create_index("idx_curation_spots_order", "curation_spots", ["curation_id", "position"])


def downgrade() -> None:
    op.drop_index("idx_curation_spots_order", table_name="curation_spots")
    op.drop_table("curation_spots")
    op.drop_index("idx_curations_feed", table_name="curations")
    op.drop_table("curations")
