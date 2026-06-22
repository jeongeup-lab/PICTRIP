"""SPT: regions, sigungus, lcls codes, spots + 4 children + user_saved_spots

Revision ID: 0003_spt_tables
Revises: 0002_usr_tables
Create Date: 2026-05-27 00:00:00

Creates the SPT (KTO 관광지 마스터) tables per DB-스키마 §Section 3, plus the
three reference tables they FK against (regions, sigungus, lcls_systm_codes).

Seeded inline:
- regions (17 시도) — stable, small, needed for spots FK to resolve

NOT seeded (populated by Dev B's W4 KTO sync worker):
- sigungus (~250) — comes from areaCode2 API
- lcls_systm_codes (~245) — comes from lclsSystmCode2 API

The `spot_embeddings` ORM model lives in `app/modules/img/models.py` (IMG
domain owns the embedding pipeline) but its DDL is in SPT because it's a
1:1 child of spots.

Per ADR-0002, SPT is the only module that gets a `repositories.py` —
introduced when KTO sync + API both reach the same table. This migration
is DDL-only; the repository file will be added when the second query
pattern actually appears (current trigger: W4).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from app.core.embedding import EMBEDDING_DIM

revision: str = "0003_spt_tables"
down_revision: str | Sequence[str] | None = "0002_usr_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# 17 시도 행정구역 코드 (2026-05 기준 — 강원/전북 특별자치도 반영).
# 통계청 행정구역 분류 앞 2자리. KTO ldongRegnCd와 동일 체계.
_REGIONS_SEED = [
    ("11", "서울특별시"),
    ("26", "부산광역시"),
    ("27", "대구광역시"),
    ("28", "인천광역시"),
    ("29", "광주광역시"),
    ("30", "대전광역시"),
    ("31", "울산광역시"),
    ("36", "세종특별자치시"),
    ("41", "경기도"),
    ("43", "충청북도"),
    ("44", "충청남도"),
    ("46", "전라남도"),
    ("47", "경상북도"),
    ("48", "경상남도"),
    ("50", "제주특별자치도"),
    ("51", "강원특별자치도"),
    ("52", "전북특별자치도"),
]


def upgrade() -> None:
    # --- Reference tables (must exist before spots FK them) ---

    regions = op.create_table(
        "regions",
        sa.Column("ldong_regn_cd", sa.String(8), primary_key=True),
        sa.Column("ldong_regn_nm", sa.String(50), nullable=False),
    )
    op.bulk_insert(
        regions,
        [{"ldong_regn_cd": code, "ldong_regn_nm": name} for code, name in _REGIONS_SEED],
    )

    op.create_table(
        "sigungus",
        sa.Column("ldong_signgu_cd", sa.String(8), primary_key=True),
        sa.Column(
            "ldong_regn_cd",
            sa.String(8),
            sa.ForeignKey("regions.ldong_regn_cd"),
            nullable=False,
            index=True,
        ),
        sa.Column("ldong_signgu_nm", sa.String(50), nullable=False),
    )

    op.create_table(
        "lcls_systm_codes",
        sa.Column("lcls_systm3_cd", sa.String(16), primary_key=True),
        sa.Column("lcls_systm2_cd", sa.String(16), nullable=True),
        sa.Column("lcls_systm1_cd", sa.String(16), nullable=True),
        sa.Column("lcls_systm3_nm", sa.String(100), nullable=False),
        sa.Column("lcls_systm2_nm", sa.String(100), nullable=True),
        sa.Column("lcls_systm1_nm", sa.String(100), nullable=True),
    )

    # --- spots master ---

    op.create_table(
        "spots",
        sa.Column("content_id", sa.String(32), primary_key=True),
        sa.Column("content_type_id", sa.SmallInteger(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("addr1", sa.String(255), nullable=True),
        sa.Column("addr2", sa.String(255), nullable=True),
        sa.Column("zipcode", sa.String(16), nullable=True),
        sa.Column("mapx", sa.Numeric(11, 8), nullable=True),
        sa.Column("mapy", sa.Numeric(10, 8), nullable=True),
        sa.Column(
            "ldong_regn_cd",
            sa.String(8),
            sa.ForeignKey("regions.ldong_regn_cd"),
            nullable=True,
        ),
        sa.Column(
            "ldong_signgu_cd",
            sa.String(8),
            sa.ForeignKey("sigungus.ldong_signgu_cd"),
            nullable=True,
        ),
        sa.Column("lcls_systm1", sa.String(16), nullable=True),
        sa.Column("lcls_systm2", sa.String(16), nullable=True),
        sa.Column(
            "lcls_systm3",
            sa.String(16),
            sa.ForeignKey("lcls_systm_codes.lcls_systm3_cd"),
            nullable=True,
        ),
        sa.Column("cpyrht_div_cd", sa.String(8), nullable=True),
        sa.Column("first_image_url", sa.String(500), nullable=True),
        sa.Column("first_image2_url", sa.String(500), nullable=True),
        sa.Column("overview", sa.Text(), nullable=True),
        sa.Column(
            "show_flag",
            sa.SmallInteger(),
            server_default=sa.text("1"),
            nullable=False,
        ),
        sa.Column("modified_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "cpyrht_div_cd IS NULL OR cpyrht_div_cd IN ('Type1','Type3')",
            name="ck_spot_cpyrht_div_cd",
        ),
        sa.CheckConstraint(
            "show_flag IN (0, 1)",
            name="ck_spot_show_flag",
        ),
    )
    op.create_index("idx_spots_location", "spots", ["mapx", "mapy"])
    op.create_index("idx_spots_region", "spots", ["ldong_regn_cd", "ldong_signgu_cd"])
    op.create_index("idx_spots_lcls", "spots", ["lcls_systm3"])
    op.create_index("idx_spots_modified", "spots", [sa.text("modified_time DESC")])
    op.create_index(
        "idx_spots_visible",
        "spots",
        ["show_flag"],
        postgresql_where=sa.text("show_flag = 1"),
    )
    op.create_index("idx_spots_type", "spots", ["content_type_id"])

    # --- 1:1 / 1:N children of spots ---

    op.create_table(
        "spot_details",
        sa.Column(
            "content_id",
            sa.String(32),
            sa.ForeignKey("spots.content_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("content_type_id", sa.SmallInteger(), nullable=False),
        sa.Column("intro_data", postgresql.JSONB(), nullable=True),
        sa.Column("info_data", postgresql.JSONB(), nullable=True),
        sa.Column("homepage", sa.String(500), nullable=True),
        sa.Column("tel", sa.String(50), nullable=True),
        sa.Column(
            "cached_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("idx_spot_details_cached", "spot_details", ["cached_at"])

    op.create_table(
        "spot_images",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "content_id",
            sa.String(32),
            sa.ForeignKey("spots.content_id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("origin_image_url", sa.String(500), nullable=False),
        sa.Column("small_image_url", sa.String(500), nullable=True),
        sa.Column("cpyrht_div_cd", sa.String(8), nullable=True),
        sa.Column("serial_num", sa.String(32), nullable=True),
        sa.Column(
            "sort_order",
            sa.SmallInteger(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )

    op.create_table(
        "spot_embeddings",
        sa.Column(
            "content_id",
            sa.String(32),
            sa.ForeignKey("spots.content_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=False),
        sa.Column("image_url", sa.String(500), nullable=True),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    # HNSW > ivfflat for 5만 row order — see DB-스키마 §Section 3.
    op.execute(
        "CREATE INDEX idx_spot_embeddings_vector ON spot_embeddings "
        "USING hnsw (embedding vector_cosine_ops)"
    )

    op.create_table(
        "spot_moods",
        sa.Column(
            "content_id",
            sa.String(32),
            sa.ForeignKey("spots.content_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "mood_id",
            sa.SmallInteger(),
            sa.ForeignKey("moods.id"),
            primary_key=True,
        ),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0",
            name="ck_spot_mood_confidence",
        ),
        sa.CheckConstraint(
            "source IN ('code','image','manual')",
            name="ck_spot_mood_source",
        ),
    )
    op.create_index(
        "idx_spot_moods_mood",
        "spot_moods",
        ["mood_id", sa.text("confidence DESC")],
    )

    # --- cross-domain: users ↔ spots ---

    op.create_table(
        "user_saved_spots",
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "content_id",
            sa.String(32),
            sa.ForeignKey("spots.content_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "saved_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "idx_user_saved_spots_user",
        "user_saved_spots",
        ["user_id", sa.text("saved_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("idx_user_saved_spots_user", table_name="user_saved_spots")
    op.drop_table("user_saved_spots")

    op.drop_index("idx_spot_moods_mood", table_name="spot_moods")
    op.drop_table("spot_moods")

    op.execute("DROP INDEX IF EXISTS idx_spot_embeddings_vector")
    op.drop_table("spot_embeddings")

    op.drop_table("spot_images")

    op.drop_index("idx_spot_details_cached", table_name="spot_details")
    op.drop_table("spot_details")

    op.drop_index("idx_spots_type", table_name="spots")
    op.drop_index("idx_spots_visible", table_name="spots")
    op.drop_index("idx_spots_modified", table_name="spots")
    op.drop_index("idx_spots_lcls", table_name="spots")
    op.drop_index("idx_spots_region", table_name="spots")
    op.drop_index("idx_spots_location", table_name="spots")
    op.drop_table("spots")

    op.drop_table("lcls_systm_codes")
    op.drop_table("sigungus")
    op.drop_table("regions")
