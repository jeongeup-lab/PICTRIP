from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.sql import false

revision: str = "0029_ai_transfer_consent"
down_revision: str | Sequence[str] | None = "0028_overseas_spot_matches"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user_consents",
        sa.Column(
            "ai_transfer_consent", sa.Boolean(), server_default=false(), nullable=False
        ),
    )
    op.add_column(
        "user_consents",
        sa.Column("ai_transfer_version", sa.String(length=16), nullable=True),
    )
    op.add_column(
        "user_consents",
        sa.Column("ai_transfer_consented_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.alter_column("user_consents", "terms_version", existing_type=sa.String(16), nullable=True)


def downgrade() -> None:
    op.alter_column("user_consents", "terms_version", existing_type=sa.String(16), nullable=False)
    op.drop_column("user_consents", "ai_transfer_consented_at")
    op.drop_column("user_consents", "ai_transfer_version")
    op.drop_column("user_consents", "ai_transfer_consent")
