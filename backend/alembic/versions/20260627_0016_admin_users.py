"""admin_users table + default admin credential (DB-backed admin auth)

Revision ID: 0016_admin_users
Revises: 0015_users_password_hash
Create Date: 2026-06-27 10:00:00

Replaces the env-var ``ADMIN_PASSWORD`` gate with a DB-stored credential so the
admin console can be provisioned/rotated through the shared CT110 DB with no
CT112 ``.env``/shell access (decision 2026-06-27).

Seeds a default ``admin`` / ``admin`` credential (bcrypt).
SECURITY: ``admin``/``admin`` is a deliberately weak default on a PUBLIC surface
(``api.pictrip.org/admin``, write access to home curation) — rotate to a strong
password ASAP (``scripts/set_admin_password.py`` or ``UPDATE admin_users``).

Hand-authored: autogenerate also wants to DROP the pg_trgm indexes
``idx_spots_addr1_trgm`` / ``idx_spots_title_trgm`` (raw SQL in migration 0008,
not ORM-declared) — those drops are spurious and intentionally excluded here.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.passwords import hash_password

revision: str = "0016_admin_users"
down_revision: str | Sequence[str] | None = "0015_users_password_hash"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "admin_users",
        sa.Column("username", sa.String(length=64), primary_key=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
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
    )

    # Seed the default admin/admin login. Hash at upgrade time (bcrypt salt is
    # random; any valid hash verifies). The table was just created so it is empty
    # — no ON CONFLICT needed. created_at/updated_at fall back to now() defaults.
    admin_users = sa.table(
        "admin_users",
        sa.column("username", sa.String),
        sa.column("password_hash", sa.String),
    )
    op.bulk_insert(
        admin_users,
        [{"username": "admin", "password_hash": hash_password("admin")}],
    )


def downgrade() -> None:
    op.drop_table("admin_users")
