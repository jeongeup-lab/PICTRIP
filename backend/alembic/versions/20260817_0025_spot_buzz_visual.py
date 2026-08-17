from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0025_spot_buzz_visual"
down_revision: str | Sequence[str] | None = "0024_travel_shorts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "spot_buzz",
        sa.Column("content_id", sa.String(length=32), primary_key=True),
        sa.Column("scope", sa.String(length=48), primary_key=True),
        sa.Column("mentions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("distinct_blogs", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("recent_ratio", sa.Float(), nullable=False, server_default="0"),
        sa.Column("blog_total", sa.Integer(), nullable=True),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("idx_spot_buzz_scope", "spot_buzz", ["scope", "mentions"])
    op.create_table(
        "spot_visual",
        sa.Column("content_id", sa.String(length=32), primary_key=True),
        sa.Column("photo_type", sa.String(length=16), nullable=False),
        sa.Column("aesthetic_score", sa.Float(), nullable=False),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("idx_spot_visual_score", "spot_visual", ["photo_type", "aesthetic_score"])


def downgrade() -> None:
    op.drop_index("idx_spot_visual_score", table_name="spot_visual")
    op.drop_table("spot_visual")
    op.drop_index("idx_spot_buzz_scope", table_name="spot_buzz")
    op.drop_table("spot_buzz")
