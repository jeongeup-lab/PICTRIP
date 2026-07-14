"""Keep domestic embeddings aligned with their source images.

Revision ID: 0019_embedding_image_consistency
Revises: 0018_overseas_spots
Create Date: 2026-07-14 00:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0019_embedding_image_consistency"
down_revision: str | Sequence[str] | None = "0018_overseas_spots"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "LOCK TABLE spots, spot_embeddings, embedding_failures IN SHARE ROW EXCLUSIVE MODE"
    )
    op.execute(
        """
        CREATE FUNCTION invalidate_spot_image_derivatives()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            DELETE FROM spot_embeddings
            WHERE content_id = NEW.content_id
              AND image_url IS DISTINCT FROM NEW.first_image_url;
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
    )
    op.execute(
        """
        INSERT INTO embedding_failures (content_id, reason, last_error)
        SELECT DISTINCT spot.content_id, 'source_changed', NULL
        FROM spots AS spot
        JOIN spot_embeddings AS embedding
          ON embedding.content_id = spot.content_id
        WHERE spot.first_image_url IS NOT NULL
          AND spot.first_image_url <> ''
          AND embedding.image_url IS DISTINCT FROM spot.first_image_url
        ON CONFLICT (content_id) DO UPDATE
        SET reason = EXCLUDED.reason,
            last_error = EXCLUDED.last_error
        """
    )
    op.execute(
        """
        DELETE FROM embedding_failures AS failure
        USING spots AS spot
        WHERE failure.content_id = spot.content_id
          AND (spot.first_image_url IS NULL OR spot.first_image_url = '')
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_spots_invalidate_image_derivatives
        AFTER UPDATE OF first_image_url ON spots
        FOR EACH ROW
        WHEN (OLD.first_image_url IS DISTINCT FROM NEW.first_image_url)
        EXECUTE FUNCTION invalidate_spot_image_derivatives()
        """
    )
    op.execute(
        """
        DELETE FROM spot_embeddings AS embedding
        USING spots AS spot
        WHERE embedding.content_id = spot.content_id
          AND embedding.image_url IS DISTINCT FROM spot.first_image_url
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_spots_invalidate_image_derivatives ON spots")
    op.execute("DROP FUNCTION IF EXISTS invalidate_spot_image_derivatives()")
