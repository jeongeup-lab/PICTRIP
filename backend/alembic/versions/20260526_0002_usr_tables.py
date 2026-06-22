"""USR: users, user_auth_providers, user_consents, user_mood_preferences

Revision ID: 0002_usr_tables
Revises: 0001_init
Create Date: 2026-05-26 00:00:00

Creates the four USR-domain tables per DB-스키마 §Section 1 and the
user_mood_preferences table per §Section 2 (the table is referenced from
both USR and TST; the ORM model lives in `app/modules/tst/models.py` —
this migration owns the DDL).

Per ADR-0002 the USR module does NOT get a `repositories.py`; selective
Repository pattern applies to SPT only. This migration is DDL-only and
introduces no service-layer indirection.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

from app.core.embedding import EMBEDDING_DIM

revision: str = "0002_usr_tables"
down_revision: str | Sequence[str] | None = "0001_init"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_MAX_5_MOODS_FN = """
CREATE OR REPLACE FUNCTION check_max_5_user_moods() RETURNS TRIGGER AS $$
BEGIN
  IF (SELECT COUNT(*) FROM user_mood_preferences WHERE user_id = NEW.user_id) >= 5 THEN
    RAISE EXCEPTION 'Maximum 5 moods allowed per user';
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;
"""


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("name", sa.String(50), nullable=True),
        sa.Column("bio", sa.String(255), nullable=True),
        sa.Column("location_label", sa.String(100), nullable=True),
        sa.Column("profile_image_url", sa.String(500), nullable=True),
        sa.Column("taste_vector", Vector(EMBEDDING_DIM), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "idx_users_email_active",
        "users",
        ["email"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.execute(
        "CREATE INDEX idx_users_taste_vector ON users "
        "USING ivfflat (taste_vector vector_cosine_ops)"
    )

    op.create_table(
        "user_auth_providers",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(16), nullable=False),
        sa.Column("provider_user_id", sa.String(255), nullable=False),
        sa.Column("refresh_token_enc", sa.Text(), nullable=True),
        sa.Column(
            "linked_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "provider IN ('kakao','google','apple','email')",
            name="ck_auth_provider_value",
        ),
        sa.UniqueConstraint(
            "provider",
            "provider_user_id",
            name="uq_auth_provider_account",
        ),
    )
    op.create_index(
        "idx_auth_providers_user",
        "user_auth_providers",
        ["user_id"],
    )

    op.create_table(
        "user_consents",
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "location_consent",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.Column(
            "photo_consent",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.Column(
            "notification_consent",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.Column("terms_version", sa.String(16), nullable=False),
        sa.Column(
            "consented_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "user_mood_preferences",
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "mood_id",
            sa.SmallInteger(),
            sa.ForeignKey("moods.id"),
            primary_key=True,
        ),
        sa.Column(
            "weight",
            sa.SmallInteger(),
            server_default=sa.text("1"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "weight BETWEEN 1 AND 5",
            name="ck_mood_pref_weight",
        ),
    )

    op.execute(_MAX_5_MOODS_FN)
    op.execute(
        "CREATE TRIGGER trg_max_5_user_moods "
        "BEFORE INSERT ON user_mood_preferences "
        "FOR EACH ROW EXECUTE FUNCTION check_max_5_user_moods()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_max_5_user_moods ON user_mood_preferences")
    op.execute("DROP FUNCTION IF EXISTS check_max_5_user_moods()")
    op.drop_table("user_mood_preferences")
    op.drop_table("user_consents")
    op.drop_index("idx_auth_providers_user", table_name="user_auth_providers")
    op.drop_table("user_auth_providers")
    op.execute("DROP INDEX IF EXISTS idx_users_taste_vector")
    op.drop_index("idx_users_email_active", table_name="users")
    op.drop_table("users")
