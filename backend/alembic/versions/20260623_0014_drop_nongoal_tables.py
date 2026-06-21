"""drop non-goal tables courses/course_days/course_items/notifications/analytics_events (M4, Stage B)

Revision ID: 0014_drop_nongoal_tables
Revises: 0013_drop_dead_columns
Create Date: 2026-06-23 00:00:00

Destructive Stage-B migration (S10 §3.1): authored in the additive branch but
applied in a separate deploy after Tasks 1-19 are live. The ORM model classes
for CRS (courses/course_days/course_items) and SYS (notifications,
analytics_events) were removed in Task 3; the tables stayed orphan in the DB.
This drops them so the DB matches the ORM.

spot_concentration is the congestion source and is PRESERVED — it is not touched
anywhere here.

downgrade() faithfully reproduces the original DDL from 0004_remaining_domains
(columns, types, nullability, server_defaults, PKs, named FKs/CHECKs, indexes,
unique constraints) so the migration roundtrips cleanly.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0014_drop_nongoal_tables"
down_revision: str | Sequence[str] | None = "0013_drop_dead_columns"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # CRS: child -> parent (FKs cascade-defined, but drop in dependency order).
    op.drop_table("course_items")
    op.drop_table("course_days")
    op.drop_table("courses")

    # SYS
    op.drop_table("notifications")
    op.drop_table("analytics_events")


def downgrade() -> None:
    # ---------- CRS §6 (parent -> child) ----------

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
