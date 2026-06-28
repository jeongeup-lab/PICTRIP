"""embedding_failures table — persistent record of failed CLIP embed attempts

Revision ID: 0017_embedding_failures
Revises: 0016_admin_users
Create Date: 2026-06-28 12:00:00

Collection (pipeline → ``spots``) and embedding (CLIP → ``spot_embeddings``) are
separate steps. A spot with ``first_image_url`` but no ``spot_embeddings`` row is
ambiguous: pending vs. permanently broken image. This table records embed
failures so the admin console can show real success/failure counts and offer a
targeted "retry failures" action. The embed job upserts on failure (bumping
``attempts``) and DELETEs on a later success, so ``count(*)`` = live failure
backlog.

Hand-authored: autogenerate also wants to DROP the pg_trgm indexes
``idx_spots_addr1_trgm`` / ``idx_spots_title_trgm`` (raw SQL in migration 0008,
not ORM-declared) — those drops are spurious and intentionally excluded here.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017_embedding_failures"
down_revision: str | Sequence[str] | None = "0016_admin_users"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "embedding_failures",
        sa.Column(
            "content_id",
            sa.String(length=32),
            sa.ForeignKey("spots.content_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("reason", sa.String(length=32), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="1", nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "first_failed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_attempt_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("idx_embedding_failures_reason", "embedding_failures", ["reason"])


def downgrade() -> None:
    op.drop_index("idx_embedding_failures_reason", table_name="embedding_failures")
    op.drop_table("embedding_failures")
