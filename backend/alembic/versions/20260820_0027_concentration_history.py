from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0027_concentration_history"
down_revision: str | Sequence[str] | None = "0026_drop_curations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "spot_concentration_daily",
        sa.Column("content_id", sa.String(length=32), nullable=False),
        sa.Column("base_ymd", sa.Date(), nullable=False),
        sa.Column("concentration_rate", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column(
            "collected_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "concentration_rate >= 0 AND concentration_rate <= 100",
            name="ck_spot_concentration_daily_rate_range",
        ),
        sa.ForeignKeyConstraint(["content_id"], ["spots.content_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("content_id", "base_ymd"),
    )
    op.create_index("idx_spot_concentration_daily_ymd", "spot_concentration_daily", ["base_ymd"])
    op.execute(
        "INSERT INTO spot_concentration_daily "
        "(content_id, base_ymd, concentration_rate, collected_at) "
        "SELECT content_id, base_ymd, concentration_rate, collected_at FROM spot_concentration "
        "ON CONFLICT DO NOTHING"
    )


def downgrade() -> None:
    op.drop_index("idx_spot_concentration_daily_ymd", table_name="spot_concentration_daily")
    op.drop_table("spot_concentration_daily")
