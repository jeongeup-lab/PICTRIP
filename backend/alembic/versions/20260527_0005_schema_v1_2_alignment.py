"""schema v1.2 alignment: halfvec, overview lazy, prototypes, TarRlteTar removal

Revision ID: 0005_schema_v1_2_alignment
Revises: 0004_remaining_domains
Create Date: 2026-05-27 15:00:00

Implements DB-스키마 v1.2 per ADR-0005 (TarRlteTar Live+Redis), ADR-0006
(halfvec serving vectors), and ADR-0007 (overview lazy, mood prototypes,
active partial indexes).

What changes
- users.taste_vector: vector(512) → halfvec(512), index → halfvec_cosine_ops
- spot_embeddings.embedding: vector(512) → halfvec(512), HNSW with explicit
  m=16, ef_construction=128
- spots.overview → spot_details.overview (lazy cache lifecycle)
- mood_prototypes (new): 8 moods × 5 spots, operator-editable in DB
- Replace 4 broad spots indexes with WHERE show_flag = 1 partial versions
- Drop related_spots, tats_name_mappings (moved to Redis-only)

What does NOT change here
- hnsw.ef_search is a session GUC, set via core/db.py asyncpg server_settings
- RecommendationLog 180d retention is documentation only (no DDL)
- Partitioning is deferred until log volume justifies the migration cost
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_schema_v1_2_alignment"
down_revision: str | Sequence[str] | None = "0004_remaining_domains"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Defensive: cloud RDS may lag behind local pgvector/pgvector:pg16 (0.8.2).
    # No-op when extension is already at the latest installed version.
    op.execute("ALTER EXTENSION vector UPDATE")

    # ---------- users.taste_vector → halfvec(512) ----------
    op.drop_index("idx_users_taste_vector", table_name="users")
    op.execute(
        "ALTER TABLE users "
        "ALTER COLUMN taste_vector TYPE halfvec(512) "
        "USING taste_vector::halfvec(512)"
    )
    op.execute(
        "CREATE INDEX idx_users_taste_vector ON users "
        "USING ivfflat (taste_vector halfvec_cosine_ops)"
    )

    # ---------- spots.overview → spot_details.overview ----------
    op.add_column("spot_details", sa.Column("overview", sa.Text(), nullable=True))
    # Defensive cross-table copy: in MVP `spots.overview` is empty (areaBasedSyncList2
    # doesn't deliver it), but a prior partial backfill could exist. Upsert keyed on
    # spot_details.content_id PK; pull content_type_id from spots to satisfy NOT NULL.
    op.execute(
        """
        INSERT INTO spot_details (content_id, content_type_id, overview, cached_at)
        SELECT content_id, content_type_id, overview, NOW()
        FROM spots
        WHERE overview IS NOT NULL AND overview <> ''
        ON CONFLICT (content_id) DO UPDATE
            SET overview = EXCLUDED.overview,
                cached_at = NOW()
        """
    )
    op.drop_column("spots", "overview")

    # ---------- spots indexes: broad → active partial (WHERE show_flag = 1) ----------
    op.drop_index("idx_spots_location", table_name="spots")
    op.drop_index("idx_spots_region", table_name="spots")
    op.drop_index("idx_spots_lcls", table_name="spots")
    op.drop_index("idx_spots_type", table_name="spots")
    op.create_index(
        "idx_spots_active_location",
        "spots",
        ["mapx", "mapy"],
        postgresql_where=sa.text("show_flag = 1"),
    )
    op.create_index(
        "idx_spots_active_region",
        "spots",
        ["ldong_regn_cd", "ldong_signgu_cd"],
        postgresql_where=sa.text("show_flag = 1"),
    )
    op.create_index(
        "idx_spots_active_lcls",
        "spots",
        ["lcls_systm3"],
        postgresql_where=sa.text("show_flag = 1"),
    )
    op.create_index(
        "idx_spots_active_type",
        "spots",
        ["content_type_id"],
        postgresql_where=sa.text("show_flag = 1"),
    )

    # ---------- spot_embeddings.embedding → halfvec(512), HNSW tuned ----------
    op.drop_index("idx_spot_embeddings_vector", table_name="spot_embeddings")
    op.execute(
        "ALTER TABLE spot_embeddings "
        "ALTER COLUMN embedding TYPE halfvec(512) "
        "USING embedding::halfvec(512)"
    )
    # m=16 / ef_construction=128 is the pgvector default for HNSW; making it
    # explicit so future readers don't have to look it up. Recall/latency
    # tuning happens via hnsw.ef_search (session GUC), not these build params.
    op.execute(
        "CREATE INDEX idx_spot_embeddings_hnsw ON spot_embeddings "
        "USING hnsw (embedding halfvec_cosine_ops) "
        "WITH (m = 16, ef_construction = 128)"
    )

    # ---------- mood_prototypes (new) ----------
    op.create_table(
        "mood_prototypes",
        sa.Column(
            "mood_id",
            sa.SmallInteger(),
            sa.ForeignKey("moods.id"),
            nullable=False,
        ),
        sa.Column(
            "content_id",
            sa.String(32),
            sa.ForeignKey("spots.content_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sort_order", sa.SmallInteger(), nullable=False),
        sa.CheckConstraint(
            "sort_order BETWEEN 1 AND 5",
            name="ck_mood_prototype_sort_order",
        ),
        sa.PrimaryKeyConstraint("mood_id", "content_id"),
        sa.UniqueConstraint("mood_id", "sort_order", name="uq_mood_prototype_order"),
    )
    op.create_index(
        "idx_mood_prototypes_order",
        "mood_prototypes",
        ["mood_id", "sort_order"],
    )

    # ---------- TarRlteTar persistence removed (Redis-only per ADR-0005) ----------
    op.drop_table("tats_name_mappings")
    op.drop_index("idx_related_rank", table_name="related_spots")
    op.drop_index("idx_related_base", table_name="related_spots")
    op.drop_table("related_spots")


def downgrade() -> None:
    # Reverse order. Re-create TarRlteTar tables first so spots FK chain stays valid.
    op.create_table(
        "related_spots",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("base_tats_cd", sa.String(64), nullable=False),
        sa.Column("base_tats_nm", sa.String(200), nullable=False),
        sa.Column("rlte_tats_cd", sa.String(64), nullable=False),
        sa.Column("rlte_tats_nm", sa.String(200), nullable=False),
        sa.Column("area_cd", sa.String(8), nullable=True),
        sa.Column("signgu_cd", sa.String(8), nullable=True),
        sa.Column("rlte_ctgry_lcls", sa.String(50), nullable=True),
        sa.Column("rlte_ctgry_mcls", sa.String(50), nullable=True),
        sa.Column("rlte_ctgry_scls", sa.String(50), nullable=True),
        sa.Column("rlte_rank", sa.SmallInteger(), nullable=True),
        sa.Column("base_ym", sa.String(6), nullable=False),
    )
    op.create_index("idx_related_base", "related_spots", ["base_tats_cd", "base_ym"])
    op.create_index("idx_related_rank", "related_spots", ["base_tats_cd", "rlte_rank"])

    op.create_table(
        "tats_name_mappings",
        sa.Column("tats_cd", sa.String(64), primary_key=True),
        sa.Column("tats_nm", sa.String(200), nullable=False),
        sa.Column(
            "matched_content_id",
            sa.String(32),
            sa.ForeignKey("spots.content_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("match_confidence", sa.Float(), nullable=True),
        sa.Column("matched_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "match_confidence IS NULL OR "
            "(match_confidence >= 0.0 AND match_confidence <= 1.0)",
            name="ck_tats_match_confidence",
        ),
    )

    op.drop_index("idx_mood_prototypes_order", table_name="mood_prototypes")
    op.drop_table("mood_prototypes")

    op.drop_index("idx_spot_embeddings_hnsw", table_name="spot_embeddings")
    op.execute(
        "ALTER TABLE spot_embeddings "
        "ALTER COLUMN embedding TYPE vector(512) "
        "USING embedding::vector(512)"
    )
    op.execute(
        "CREATE INDEX idx_spot_embeddings_vector ON spot_embeddings "
        "USING hnsw (embedding vector_cosine_ops)"
    )

    op.drop_index("idx_spots_active_type", table_name="spots")
    op.drop_index("idx_spots_active_lcls", table_name="spots")
    op.drop_index("idx_spots_active_region", table_name="spots")
    op.drop_index("idx_spots_active_location", table_name="spots")
    op.create_index("idx_spots_type", "spots", ["content_type_id"])
    op.create_index("idx_spots_lcls", "spots", ["lcls_systm3"])
    op.create_index("idx_spots_region", "spots", ["ldong_regn_cd", "ldong_signgu_cd"])
    op.create_index("idx_spots_location", "spots", ["mapx", "mapy"])

    op.add_column("spots", sa.Column("overview", sa.Text(), nullable=True))
    op.execute(
        """
        UPDATE spots s
        SET overview = sd.overview
        FROM spot_details sd
        WHERE sd.content_id = s.content_id
          AND sd.overview IS NOT NULL
          AND sd.overview <> ''
        """
    )
    op.drop_column("spot_details", "overview")

    op.drop_index("idx_users_taste_vector", table_name="users")
    op.execute(
        "ALTER TABLE users "
        "ALTER COLUMN taste_vector TYPE vector(512) "
        "USING taste_vector::vector(512)"
    )
    op.execute(
        "CREATE INDEX idx_users_taste_vector ON users "
        "USING ivfflat (taste_vector vector_cosine_ops)"
    )
