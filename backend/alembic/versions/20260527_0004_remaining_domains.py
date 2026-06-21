"""remaining domains: TST feedback, REC, Collection, CRS, TarRlteTar, DataLab, SYS

Revision ID: 0004_remaining_domains
Revises: 0003_spt_tables
Create Date: 2026-05-27 12:00:00

Single migration that closes out the rest of DB-스키마 §§2.feedback / 4 / 5 / 6 /
7 / 8 / 10. After this, every persistent table in the spec exists in the DB.

Why one migration: each section is small (1 to 3 tables), heavily interlinked
through users / spots FKs that already exist after 0002 + 0003, and the
solo-dev profile prefers fewer files to keep the alembic versions/ dir
scannable.

Notable choices:
- Every BIGINT id is `BigInteger` (schema spec is `bigint id PK` throughout)
- enum-style varchars get CHECK constraints, never lookup tables (over-eng)
- recommendation_logs.input_payload gets a GIN index for filter-on-jsonb
- reason_cache + DataLab visitor tables get the unique-lookup indexes the
  spec calls out as cache keys / dedup keys
- collection_spots has a composite PK; collection slug is unique
- analytics_events / kto_api_logs get a created_at index for retention sweeps
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_remaining_domains"
down_revision: str | Sequence[str] | None = "0003_spt_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ---------- TST §2 (feedback) ----------

    op.create_table(
        "taste_feedback_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("content_id", sa.String(32), nullable=False),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "action IN ('like','save','skip','view')",
            name="ck_taste_feedback_action",
        ),
    )
    op.create_index(
        "idx_taste_feedback_user_recent",
        "taste_feedback_events",
        ["user_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "idx_taste_feedback_content",
        "taste_feedback_events",
        ["content_id"],
    )

    # ---------- REC §4 ----------

    op.create_table(
        "recommendation_logs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("input_payload", postgresql.JSONB(), nullable=False),
        sa.Column("results", postgresql.JSONB(), nullable=False),
        sa.Column("algorithm_version", sa.String(16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "source_type IN ('photo','mood','today_inspo','similar','search')",
            name="ck_rec_log_source_type",
        ),
    )
    op.create_index(
        "idx_rec_logs_user_recent",
        "recommendation_logs",
        ["user_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "idx_rec_logs_source",
        "recommendation_logs",
        ["source_type", "created_at"],
    )
    op.create_index(
        "idx_rec_logs_input",
        "recommendation_logs",
        ["input_payload"],
        postgresql_using="gin",
    )

    op.create_table(
        "reason_cache",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_taste_hash", sa.String(64), nullable=False),
        sa.Column(
            "content_id",
            sa.String(32),
            sa.ForeignKey("spots.content_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("reason_text", sa.Text(), nullable=False),
        sa.Column("llm_version", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "idx_reason_cache_lookup",
        "reason_cache",
        ["user_taste_hash", "content_id"],
        unique=True,
    )
    op.create_index("idx_reason_cache_expires", "reason_cache", ["expires_at"])

    # ---------- Collection §5 (lives in SPT module) ----------

    op.create_table(
        "collections",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("slug", sa.String(64), nullable=False, unique=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("cover_image_url", sa.String(500), nullable=True),
        sa.Column(
            "curator_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "priority",
            sa.SmallInteger(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "idx_collections_published",
        "collections",
        [sa.text("published_at DESC")],
        postgresql_where=sa.text("archived_at IS NULL"),
    )

    op.create_table(
        "collection_spots",
        sa.Column(
            "collection_id",
            sa.BigInteger(),
            sa.ForeignKey("collections.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "content_id",
            sa.String(32),
            sa.ForeignKey("spots.content_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
    )
    op.create_index(
        "idx_collection_spots_order",
        "collection_spots",
        ["collection_id", "position"],
    )

    # ---------- CRS §6 ----------

    op.create_table(
        "courses",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column(
            "base_content_id",
            sa.String(32),
            sa.ForeignKey("spots.content_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("duration_type", sa.String(16), nullable=False),
        sa.Column("pace_type", sa.String(16), nullable=False),
        sa.Column("companion_type", sa.String(16), nullable=False),
        sa.Column("course_type", sa.String(16), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
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
            "duration_type IN ('day','1n2d','2n3d','3n_plus')",
            name="ck_course_duration_type",
        ),
        sa.CheckConstraint(
            "pace_type IN ('easy','normal','packed')",
            name="ck_course_pace_type",
        ),
        sa.CheckConstraint(
            "companion_type IN ('solo','couple','friends','family')",
            name="ck_course_companion_type",
        ),
        sa.CheckConstraint(
            "course_type IN ('efficient','mood','calm')",
            name="ck_course_course_type",
        ),
    )
    op.create_index(
        "idx_courses_user",
        "courses",
        ["user_id", sa.text("updated_at DESC")],
    )

    op.create_table(
        "course_days",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "course_id",
            sa.BigInteger(),
            sa.ForeignKey("courses.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("day_number", sa.SmallInteger(), nullable=False),
        sa.Column("total_km", sa.Numeric(7, 2), nullable=True),
        sa.Column("estimated_hours", sa.SmallInteger(), nullable=True),
        sa.UniqueConstraint("course_id", "day_number", name="uq_course_day_number"),
    )

    op.create_table(
        "course_items",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "course_day_id",
            sa.BigInteger(),
            sa.ForeignKey("course_days.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "content_id",
            sa.String(32),
            sa.ForeignKey("spots.content_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.Column("scheduled_time", sa.Time(), nullable=True),
        sa.Column("stay_minutes", sa.SmallInteger(), nullable=True),
    )
    op.create_index(
        "idx_course_items_day",
        "course_items",
        ["course_day_id", "position"],
    )

    # ---------- TarRlteTar §7 (lives in SPT module) ----------

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
            "match_confidence IS NULL OR (match_confidence >= 0.0 AND match_confidence <= 1.0)",
            name="ck_tats_match_confidence",
        ),
    )

    # ---------- DataLab §8 (MAP module) ----------

    op.create_table(
        "region_visitors",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "ldong_regn_cd",
            sa.String(8),
            sa.ForeignKey("regions.ldong_regn_cd"),
            nullable=False,
            index=True,
        ),
        sa.Column("base_date", sa.Date(), nullable=False),
        sa.Column("day_of_week", sa.SmallInteger(), nullable=False),
        sa.Column("tou_div_cd", sa.String(4), nullable=False),
        sa.Column("tou_num", sa.Numeric(14, 2), nullable=False),
        sa.CheckConstraint("day_of_week BETWEEN 1 AND 7", name="ck_region_visitor_dow"),
        sa.CheckConstraint("tou_div_cd IN ('1','2','3')", name="ck_region_visitor_tou_div"),
    )
    op.create_index(
        "idx_region_visitors_unique",
        "region_visitors",
        ["ldong_regn_cd", "base_date", "tou_div_cd"],
        unique=True,
    )

    op.create_table(
        "sigungu_visitors",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "ldong_signgu_cd",
            sa.String(8),
            sa.ForeignKey("sigungus.ldong_signgu_cd"),
            nullable=False,
            index=True,
        ),
        sa.Column("base_date", sa.Date(), nullable=False),
        sa.Column("day_of_week", sa.SmallInteger(), nullable=False),
        sa.Column("tou_div_cd", sa.String(4), nullable=False),
        sa.Column("tou_num", sa.Numeric(14, 2), nullable=False),
        sa.CheckConstraint("day_of_week BETWEEN 1 AND 7", name="ck_sigungu_visitor_dow"),
        sa.CheckConstraint("tou_div_cd IN ('1','2','3')", name="ck_sigungu_visitor_tou_div"),
    )
    op.create_index(
        "idx_sigungu_visitors_unique",
        "sigungu_visitors",
        ["ldong_signgu_cd", "base_date", "tou_div_cd"],
        unique=True,
    )

    # ---------- SYS §10 ----------

    op.create_table(
        "notifications",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "type IN ('collection','saved_update','course_rec','crowd_change')",
            name="ck_notification_type",
        ),
    )
    op.create_index(
        "idx_notifications_user_unread",
        "notifications",
        ["user_id", sa.text("created_at DESC")],
        postgresql_where=sa.text("read_at IS NULL"),
    )

    op.create_table(
        "analytics_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("event_name", sa.String(64), nullable=False),
        sa.Column("properties", postgresql.JSONB(), nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("idx_analytics_old", "analytics_events", ["occurred_at"])
    op.create_index(
        "idx_analytics_user_event",
        "analytics_events",
        ["user_id", "event_name", sa.text("occurred_at DESC")],
    )

    op.create_table(
        "search_history",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("query", sa.String(200), nullable=False),
        sa.Column("filter", postgresql.JSONB(), nullable=True),
        sa.Column(
            "searched_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "idx_search_history_user",
        "search_history",
        ["user_id", sa.text("searched_at DESC")],
    )

    op.create_table(
        "photo_search_sessions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("results_count", sa.SmallInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "kto_api_logs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("api_name", sa.String(32), nullable=False),
        sa.Column("operation", sa.String(64), nullable=False),
        sa.Column("status_code", sa.SmallInteger(), nullable=False),
        sa.Column("response_ms", sa.Integer(), nullable=False),
        sa.Column(
            "called_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "idx_kto_api_logs_called",
        "kto_api_logs",
        ["api_name", sa.text("called_at DESC")],
    )

    op.create_table(
        "kto_sync_runs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("sync_type", sa.String(32), nullable=False, index=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "items_added",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "items_updated",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "items_deactivated",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("error_log", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    # SYS
    op.drop_table("kto_sync_runs")
    op.drop_index("idx_kto_api_logs_called", table_name="kto_api_logs")
    op.drop_table("kto_api_logs")
    op.drop_table("photo_search_sessions")
    op.drop_index("idx_search_history_user", table_name="search_history")
    op.drop_table("search_history")
    op.drop_index("idx_analytics_user_event", table_name="analytics_events")
    op.drop_index("idx_analytics_old", table_name="analytics_events")
    op.drop_table("analytics_events")
    op.drop_index("idx_notifications_user_unread", table_name="notifications")
    op.drop_table("notifications")

    # DataLab
    op.drop_index("idx_sigungu_visitors_unique", table_name="sigungu_visitors")
    op.drop_table("sigungu_visitors")
    op.drop_index("idx_region_visitors_unique", table_name="region_visitors")
    op.drop_table("region_visitors")

    # TarRlteTar
    op.drop_table("tats_name_mappings")
    op.drop_index("idx_related_rank", table_name="related_spots")
    op.drop_index("idx_related_base", table_name="related_spots")
    op.drop_table("related_spots")

    # CRS
    op.drop_index("idx_course_items_day", table_name="course_items")
    op.drop_table("course_items")
    op.drop_table("course_days")
    op.drop_index("idx_courses_user", table_name="courses")
    op.drop_table("courses")

    # Collection
    op.drop_index("idx_collection_spots_order", table_name="collection_spots")
    op.drop_table("collection_spots")
    op.drop_index("idx_collections_published", table_name="collections")
    op.drop_table("collections")

    # REC
    op.drop_index("idx_reason_cache_expires", table_name="reason_cache")
    op.drop_index("idx_reason_cache_lookup", table_name="reason_cache")
    op.drop_table("reason_cache")
    op.drop_index("idx_rec_logs_input", table_name="recommendation_logs")
    op.drop_index("idx_rec_logs_source", table_name="recommendation_logs")
    op.drop_index("idx_rec_logs_user_recent", table_name="recommendation_logs")
    op.drop_table("recommendation_logs")

    # TST
    op.drop_index("idx_taste_feedback_content", table_name="taste_feedback_events")
    op.drop_index("idx_taste_feedback_user_recent", table_name="taste_feedback_events")
    op.drop_table("taste_feedback_events")
