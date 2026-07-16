"""Gallery (multi-image) centroid embeddings for matching quality.

Revision ID: 0020_spot_embeddings_gallery
Revises: 0019_embedding_image_consistency
Create Date: 2026-07-17 00:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import HALFVEC

revision: str = "0020_spot_embeddings_gallery"
down_revision: str | Sequence[str] | None = "0019_embedding_image_consistency"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DERIVATIVES_FN_WITH_GALLERY = """
CREATE OR REPLACE FUNCTION invalidate_spot_image_derivatives()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    DELETE FROM spot_embeddings
    WHERE content_id = NEW.content_id
      AND (
          NEW.first_image_url IS NULL
          OR NEW.first_image_url = ''
          OR image_url IS DISTINCT FROM NEW.first_image_url
      );
    DELETE FROM spot_embeddings_gallery
    WHERE content_id = NEW.content_id
      AND (
          NEW.first_image_url IS NULL
          OR NEW.first_image_url = ''
          OR image_url IS DISTINCT FROM NEW.first_image_url
      );
    IF NEW.first_image_url IS NULL OR NEW.first_image_url = '' THEN
        DELETE FROM embedding_failures
        WHERE content_id = NEW.content_id;
    ELSE
        INSERT INTO embedding_failures (content_id, reason, last_error)
        VALUES (NEW.content_id, 'source_changed', NULL)
        ON CONFLICT (content_id) DO UPDATE
        SET reason = EXCLUDED.reason,
            last_error = EXCLUDED.last_error;
    END IF;
    RETURN NEW;
END;
$$
"""

_DERIVATIVES_FN_WITHOUT_GALLERY = """
CREATE OR REPLACE FUNCTION invalidate_spot_image_derivatives()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    DELETE FROM spot_embeddings
    WHERE content_id = NEW.content_id
      AND (
          NEW.first_image_url IS NULL
          OR NEW.first_image_url = ''
          OR image_url IS DISTINCT FROM NEW.first_image_url
      );
    IF NEW.first_image_url IS NULL OR NEW.first_image_url = '' THEN
        DELETE FROM embedding_failures
        WHERE content_id = NEW.content_id;
    ELSE
        INSERT INTO embedding_failures (content_id, reason, last_error)
        VALUES (NEW.content_id, 'source_changed', NULL)
        ON CONFLICT (content_id) DO UPDATE
        SET reason = EXCLUDED.reason,
            last_error = EXCLUDED.last_error;
    END IF;
    RETURN NEW;
END;
$$
"""


def upgrade() -> None:
    op.create_table(
        "spot_embeddings_gallery",
        sa.Column(
            "content_id",
            sa.String(length=32),
            sa.ForeignKey("spots.content_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("embedding", HALFVEC(512), nullable=False),
        sa.Column("image_url", sa.String(length=500), nullable=False),
        sa.Column("image_count", sa.SmallInteger(), nullable=False),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "idx_spot_embeddings_gallery_hnsw",
        "spot_embeddings_gallery",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "halfvec_cosine_ops"},
        postgresql_with={"m": 16, "ef_construction": 128},
    )
    op.execute(_DERIVATIVES_FN_WITH_GALLERY)


def downgrade() -> None:
    op.execute(_DERIVATIVES_FN_WITHOUT_GALLERY)
    op.drop_index("idx_spot_embeddings_gallery_hnsw", table_name="spot_embeddings_gallery")
    op.drop_table("spot_embeddings_gallery")
