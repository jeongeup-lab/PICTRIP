"""drop dead columns refresh_token_enc + notification_consent (M3, Stage B)

Revision ID: 0013_drop_dead_columns
Revises: 0012_spots_image_pool_idx
Create Date: 2026-06-23 00:00:00

Destructive Stage-B migration (S10 §3.1): authored in the additive branch but
applied in a separate deploy after Tasks 1-19 are live and serve as the rollback
target. The ORM already stopped referencing both columns — refresh_token_enc
(auth rewrite, Task 6) and notification_consent (ORM mapping removed, Task 13) —
so after this migration the DB matches the ORM.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013_drop_dead_columns"
down_revision: str | Sequence[str] | None = "0012_spots_image_pool_idx"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("user_auth_providers", "refresh_token_enc")
    op.drop_column("user_consents", "notification_consent")


def downgrade() -> None:
    op.add_column(
        "user_consents",
        sa.Column(
            "notification_consent",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "user_auth_providers",
        sa.Column("refresh_token_enc", sa.Text(), nullable=True),
    )
