from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0026_drop_curations"
down_revision: str | Sequence[str] | None = "0025_spot_buzz_visual"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("curation_spots")
    op.drop_table("curations")


def downgrade() -> None:
    op.create_table(
        "curations",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("type", sa.String(length=16), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("subtitle", sa.Text(), nullable=True),
        sa.Column("lead", sa.Text(), nullable=True),
        sa.Column("intro", sa.Text(), nullable=True),
        sa.Column(
            "cover_spot_id",
            sa.String(length=32),
            sa.ForeignKey("spots.content_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "region_cd",
            sa.String(length=8),
            sa.ForeignKey("regions.ldong_regn_cd"),
            nullable=True,
        ),
        sa.Column("mood_id", sa.SmallInteger(), sa.ForeignKey("moods.id"), nullable=True),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "(type = 'region' AND region_cd IS NOT NULL) "
            "OR (type = 'mood' AND mood_id IS NOT NULL) "
            "OR (type = 'editorial')",
            name="ck_curation_scope",
        ),
        sa.CheckConstraint(
            "type IN ('region', 'mood', 'editorial')",
            name="ck_curation_type",
        ),
        sa.UniqueConstraint("slug", name="uq_curations_slug"),
    )
    op.create_index("idx_curations_feed", "curations", ["type", "is_published", "position"])
    op.create_table(
        "curation_spots",
        sa.Column(
            "curation_id",
            sa.BigInteger(),
            sa.ForeignKey("curations.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "content_id",
            sa.String(length=32),
            sa.ForeignKey("spots.content_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
    )
    op.create_index("idx_curation_spots_order", "curation_spots", ["curation_id", "position"])
