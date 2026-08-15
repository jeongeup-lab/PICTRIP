from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0024_travel_shorts"
down_revision: str | Sequence[str] | None = "0023_apple_refresh_token"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "travel_shorts",
        sa.Column("video_id", sa.String(length=16), primary_key=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("channel_title", sa.Text(), nullable=False),
        sa.Column("thumbnail_url", sa.Text(), nullable=False),
        sa.Column("view_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("duration_sec", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("anchor_label", sa.String(length=80), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("idx_travel_shorts_rank", "travel_shorts", ["rank"])
    op.create_table(
        "travel_shorts_spots",
        sa.Column(
            "video_id",
            sa.String(length=16),
            sa.ForeignKey("travel_shorts.video_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("content_id", sa.String(length=32), primary_key=True),
        sa.Column("rank", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_table("travel_shorts_spots")
    op.drop_index("idx_travel_shorts_rank", table_name="travel_shorts")
    op.drop_table("travel_shorts")
