"""overseas_spots table + feed module foundation (S13 redesign)

Revision ID: 0018_overseas_spots
Revises: 0017_embedding_failures
Create Date: 2026-07-12 00:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018_overseas_spots"
down_revision: str | Sequence[str] | None = "0017_embedding_failures"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "overseas_spots",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("wikidata_id", sa.String(length=32), nullable=False),
        sa.Column("name_ko", sa.String(length=255), nullable=False),
        sa.Column("name_en", sa.String(length=255), nullable=True),
        sa.Column("country_code", sa.String(length=2), nullable=False),
        sa.Column("country_name_ko", sa.String(length=80), nullable=False),
        sa.Column("description_ko", sa.Text(), nullable=True),
        sa.Column("image_url", sa.Text(), nullable=False),
        sa.Column("image_author", sa.Text(), nullable=True),
        sa.Column("image_license", sa.String(length=80), nullable=True),
        sa.Column("image_license_url", sa.Text(), nullable=True),
        sa.Column("image_source_url", sa.Text(), nullable=False),
        sa.Column("fame_score", sa.Integer(), server_default="0", nullable=False),
        sa.Column("category", sa.String(length=40), nullable=True),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lng", sa.Float(), nullable=True),
        sa.Column("is_hidden", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("wikidata_id", name="uq_overseas_spots_wikidata_id"),
    )
    op.execute("ALTER TABLE overseas_spots ADD COLUMN embedding halfvec(512)")
    op.execute(
        "CREATE INDEX idx_overseas_spots_hnsw ON overseas_spots "
        "USING hnsw (embedding halfvec_cosine_ops) WITH (m = 16, ef_construction = 128)"
    )
    op.execute(
        "CREATE INDEX idx_overseas_spots_visible ON overseas_spots (is_hidden, fame_score DESC)"
    )


def downgrade() -> None:
    op.drop_table("overseas_spots")
