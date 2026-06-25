"""add users.password_hash for email/password login

Revision ID: 0015_users_password_hash
Revises: 0014_drop_nongoal_tables
Create Date: 2026-06-25 16:01:00

Adds a single nullable column ``users.password_hash`` (bcrypt hash) so the new
email/password auth path (S09) can store credentials alongside OAuth identities.
Nullable because OAuth-only accounts have no password.

Authored by hand: autogenerate also wants to DROP the pg_trgm indexes
``idx_spots_addr1_trgm`` / ``idx_spots_title_trgm`` (raw-SQL in migration 0008,
not ORM-declared) — those drops are spurious and intentionally excluded here.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015_users_password_hash"
down_revision: str | Sequence[str] | None = "0014_drop_nongoal_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("password_hash", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "password_hash")
