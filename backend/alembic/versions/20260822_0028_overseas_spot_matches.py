from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0028_overseas_spot_matches"
down_revision: str | Sequence[str] | None = "0027_concentration_history"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "overseas_spot_matches",
        sa.Column("overseas_id", sa.BigInteger(), nullable=False),
        sa.Column("rank", sa.SmallInteger(), nullable=False),
        sa.Column("content_id", sa.String(length=32), nullable=False),
        sa.Column("distance", sa.Float(), nullable=False),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("rank BETWEEN 1 AND 3", name="ck_overseas_spot_matches_rank_range"),
        sa.ForeignKeyConstraint(["overseas_id"], ["overseas_spots.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["content_id"], ["spots.content_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("overseas_id", "rank"),
    )
    op.create_index("idx_overseas_spot_matches_content", "overseas_spot_matches", ["content_id"])


def downgrade() -> None:
    op.drop_index("idx_overseas_spot_matches_content", table_name="overseas_spot_matches")
    op.drop_table("overseas_spot_matches")
