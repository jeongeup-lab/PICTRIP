"""USR: user_sessions, user_devices (DB-스키마 v1.2 §Section 1)

Revision ID: 0007_usr_sessions_devices
Revises: 0006_spot_images_unique_sort
Create Date: 2026-05-31 00:00:00

Adds the two USR v1.2 tables that were missing from the backend:

- ``user_sessions`` — access-token issue/expiry tracking, keyed by JWT jti.
- ``user_devices`` — per-device login metadata (platform + push token).

Per ADR-0007 the MVP uses ``user_sessions`` for access-token expiry management
only; ``refresh_tokens`` is deferred to v1.1 and is intentionally NOT created
here. Both tables CASCADE-delete with ``users`` (account deletion, USR-010).

Index/constraint names match the ORM (`app/modules/usr/models.py`) so
``alembic check`` stays clean.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_usr_sessions_devices"
down_revision: str | Sequence[str] | None = "0006_spot_images_unique_sort"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_sessions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("jwt_id", sa.String(64), nullable=False),
        sa.Column("device_fingerprint", sa.String(255), nullable=True),
        sa.Column(
            "issued_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("jwt_id", name="uq_user_sessions_jwt_id"),
    )
    op.create_index("idx_user_sessions_user", "user_sessions", ["user_id"])
    op.create_index("idx_user_sessions_expires", "user_sessions", ["expires_at"])

    op.create_table(
        "user_devices",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("platform", sa.String(16), nullable=False),
        sa.Column("push_token", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "platform IN ('ios','android','web')",
            name="ck_user_devices_platform",
        ),
        sa.UniqueConstraint("user_id", "push_token", name="uq_user_devices_user_token"),
    )
    op.create_index("idx_user_devices_user", "user_devices", ["user_id"])


def downgrade() -> None:
    op.drop_index("idx_user_devices_user", table_name="user_devices")
    op.drop_table("user_devices")
    op.drop_index("idx_user_sessions_expires", table_name="user_sessions")
    op.drop_index("idx_user_sessions_user", table_name="user_sessions")
    op.drop_table("user_sessions")
