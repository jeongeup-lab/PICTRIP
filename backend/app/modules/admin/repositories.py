"""admin repositories — read-only cross-module aggregates (A01 §1.1).

The *only* admin file that imports SQLAlchemy. All access is read-only:

- ``sync_runs`` is owned by pipeline/ (A05) → accessed via raw ``text()`` only,
  no ORM model, never in ``Base``/Alembic. Column names are the measured schema
  (A01 §0) and shared with pipeline/ (rename breaks both — see PR notes).
- ``spots`` / ``users`` / ``user_auth_providers`` aggregates use raw SQL too,
  keeping this layer uniform and free of cross-module model imports.

Functions return plain Python (``Row`` / ``dict`` / scalars), never Pydantic —
shaping into DTOs is the service layer's job.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import Row, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession


async def count_spots(session: AsyncSession) -> int:
    result = await session.execute(text("SELECT count(*) FROM spots"))
    return int(result.scalar_one())


async def latest_sync_run(session: AsyncSession) -> Row[Any] | None:
    """Newest run (idx_sync_runs_recent, id DESC). ``None`` if never synced."""
    result = await session.execute(
        text(
            "SELECT id, started_at, finished_at, status, mode, api_calls, "
            "inserted, updated, soft_deleted, duration_sec "
            "FROM sync_runs ORDER BY id DESC LIMIT 1"
        )
    )
    return result.first()


async def sync_run_daily_counts(session: AsyncSession, days: int) -> list[Row[Any]]:
    """Per-day rollup over the last ``days`` calendar days (most recent first)."""
    result = await session.execute(
        text(
            "SELECT started_at::date AS day, "
            "count(*) FILTER (WHERE status = 'success') AS success, "
            "count(*) FILTER (WHERE status = 'error') AS error, "
            "count(*) FILTER (WHERE status = 'running') AS running, "
            "count(*) AS runs "
            "FROM sync_runs "
            "WHERE started_at::date >= (CURRENT_DATE - make_interval(days => :days - 1)) "
            "GROUP BY started_at::date "
            "ORDER BY day DESC"
        ),
        {"days": days},
    )
    return list(result.all())


async def sync_runs_on_date(session: AsyncSession, day: date) -> list[Row[Any]]:
    """All runs whose ``started_at`` date equals ``day`` (chronological)."""
    result = await session.execute(
        text(
            "SELECT id, status, mode, started_at, finished_at, api_calls, "
            "inserted, updated, soft_deleted, duration_sec, error "
            "FROM sync_runs WHERE started_at::date = :day ORDER BY id ASC"
        ),
        {"day": day},
    )
    return list(result.all())


async def db_ping(session: AsyncSession) -> bool:
    """``SELECT 1`` liveness probe; False on any failure."""
    try:
        result = await session.execute(text("SELECT 1"))
        return bool(result.scalar_one() == 1)
    except (SQLAlchemyError, OSError):
        # DB/connection errors → degrade to "not ok". Unexpected exceptions
        # (programming errors etc.) propagate.
        return False


async def user_aggregates(session: AsyncSession) -> Row[Any]:
    """Total / active / new-7d / deleted-30d / kakao counts in one round-trip."""
    result = await session.execute(
        text(
            "SELECT "
            "count(*) AS total, "
            "count(*) FILTER (WHERE deleted_at IS NULL) AS active, "
            "count(*) FILTER (WHERE created_at >= now() - interval '7 days') AS new7d, "
            "count(*) FILTER (WHERE deleted_at >= now() - interval '30 days') AS deleted30d, "
            "(SELECT count(*) FROM user_auth_providers WHERE provider = 'kakao') AS kakao "
            "FROM users"
        )
    )
    return result.one()
