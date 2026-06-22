"""drop 15 unused 'future-feature' tables (schema-ahead-of-code cleanup)

Revision ID: 0010_drop_dead_tables
Revises: 0009_spt_concentration
Create Date: 2026-06-07 00:00:00

These tables were created in 0002 / 0004 / 0005 / 0007 as a schema-ahead-of-code
bet on features that never shipped. None is read or written by any service,
route or worker — they are pure dead weight that makes the schema lie about what
the app does. This migration drops them so schema == code:

- USR:  user_sessions, user_devices, user_mood_preferences (+ its max-5 trigger)
- TST:  taste_feedback_events
- REC:  recommendation_logs, reason_cache
- SPT:  mood_prototypes, collections, collection_spots
- MAP:  region_visitors, sigungu_visitors
- SYS:  search_history, photo_search_sessions, kto_api_logs, kto_sync_runs

Live SYS tables (notifications, analytics_events) and live CRS tables (courses,
course_days, course_items) are untouched.

`downgrade()` recreates every table (structure + indexes + the max-5 trigger)
verbatim from the original migrations, so the round-trip is reversible. The
`mood_prototypes` seed was never populated by a migration, so there is nothing
to re-seed. Postgres DROP TABLE cascades the table's own indexes, so `upgrade()`
needs no explicit drop_index.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010_drop_dead_tables"
down_revision: str | Sequence[str] | None = "0009_spt_concentration"
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
    # USR — sessions / devices (0007)
    op.drop_table("user_devices")
    op.drop_table("user_sessions")

    # USR/TST — mood preferences + its max-5 trigger/function (0002); trigger first
    op.execute("DROP TRIGGER IF EXISTS trg_max_5_user_moods ON user_mood_preferences")
    op.execute("DROP FUNCTION IF EXISTS check_max_5_user_moods()")
    op.drop_table("user_mood_preferences")

    # TST — feedback (0004)
    op.drop_table("taste_feedback_events")

    # REC — logs + reason cache (0004)
    op.drop_table("reason_cache")
    op.drop_table("recommendation_logs")

    # SPT — mood prototypes (0005) + collections (0004); child before parent
    op.drop_table("mood_prototypes")
    op.drop_table("collection_spots")
    op.drop_table("collections")

    # MAP — DataLab visitor counts (0004)
    op.drop_table("sigungu_visitors")
    op.drop_table("region_visitors")

    # SYS — search / photo-search / KTO audit + sync logs (0004)
    op.drop_table("kto_sync_runs")
    op.drop_table("kto_api_logs")
    op.drop_table("photo_search_sessions")
    op.drop_table("search_history")


def downgrade() -> None:
    # ---------- USR sessions / devices (0007) ----------
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

    # ---------- USR/TST mood preferences + max-5 trigger (0002) ----------
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
        sa.CheckConstraint("weight BETWEEN 1 AND 5", name="ck_mood_pref_weight"),
    )
    op.execute(_MAX_5_MOODS_FN)
    op.execute(
        "CREATE TRIGGER trg_max_5_user_moods "
        "BEFORE INSERT ON user_mood_preferences "
        "FOR EACH ROW EXECUTE FUNCTION check_max_5_user_moods()"
    )

    # ---------- TST feedback (0004) ----------
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
    op.create_index("idx_taste_feedback_content", "taste_feedback_events", ["content_id"])

    # ---------- REC logs + reason cache (0004) ----------
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
    op.create_index("idx_rec_logs_source", "recommendation_logs", ["source_type", "created_at"])
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

    # ---------- SPT collections (0004) + mood prototypes (0005) ----------
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
        sa.Column("priority", sa.SmallInteger(), server_default=sa.text("0"), nullable=False),
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

    op.create_table(
        "mood_prototypes",
        sa.Column("mood_id", sa.SmallInteger(), sa.ForeignKey("moods.id"), nullable=False),
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
    op.create_index("idx_mood_prototypes_order", "mood_prototypes", ["mood_id", "sort_order"])

    # ---------- MAP DataLab visitor counts (0004) ----------
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

    # ---------- SYS search / photo-search / KTO audit + sync logs (0004) ----------
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
        sa.Column("items_added", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("items_updated", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("items_deactivated", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("error_log", sa.Text(), nullable=True),
    )
