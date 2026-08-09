from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0023_apple_refresh_token"
down_revision: str | Sequence[str] | None = "0022_plan_public_id"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user_auth_providers",
        sa.Column("provider_refresh_token", sa.String(length=512), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_auth_providers", "provider_refresh_token")
