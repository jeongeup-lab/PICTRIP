from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import Row, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admin.models import AdminUser


async def get_admin_user(session: AsyncSession, username: str) -> AdminUser | None:
    return (
        await session.execute(select(AdminUser).where(AdminUser.username == username))
    ).scalar_one_or_none()


async def count_spots(session: AsyncSession) -> int:
    result = await session.execute(text("SELECT count(*) FROM spots"))
    return int(result.scalar_one())


async def count_embeddings(session: AsyncSession) -> int:
    result = await session.execute(
        text(
            "SELECT count(*) FROM spot_embeddings e JOIN spots s "
            "ON s.content_id = e.content_id AND s.first_image_url = e.image_url"
        )
    )
    return int(result.scalar_one())


async def latest_sync_run(session: AsyncSession) -> Row[Any] | None:
    result = await session.execute(
        text(
            "SELECT id, started_at, finished_at, status, mode, api_calls, "
            "inserted, updated, soft_deleted, duration_sec "
            "FROM sync_runs ORDER BY id DESC LIMIT 1"
        )
    )
    return result.first()


async def sync_run_daily_counts(session: AsyncSession, days: int) -> list[Row[Any]]:
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
    result = await session.execute(
        text(
            "SELECT id, status, mode, started_at, finished_at, api_calls, "
            "inserted, updated, soft_deleted, duration_sec, error "
            "FROM sync_runs WHERE started_at::date = :day ORDER BY id ASC"
        ),
        {"day": day},
    )
    return list(result.all())


async def embedding_totals(session: AsyncSession) -> Row[Any]:
    result = await session.execute(
        text(
            "SELECT "
            "(SELECT count(*) FROM spots) AS total_spots, "
            "(SELECT count(*) FROM spots WHERE first_image_url IS NOT NULL "
            "   AND first_image_url <> '') AS with_image, "
            "(SELECT count(*) FROM spots s WHERE s.first_image_url IS NOT NULL "
            "   AND s.first_image_url <> '' AND NOT EXISTS "
            "   (SELECT 1 FROM spot_embeddings e WHERE e.content_id = s.content_id "
            "      AND e.image_url = s.first_image_url)) AS missing, "
            "(SELECT count(*) FROM embedding_failures f JOIN spots s "
            "   ON s.content_id = f.content_id "
            " WHERE s.first_image_url IS NOT NULL AND s.first_image_url <> '' "
            "   AND NOT EXISTS (SELECT 1 FROM spot_embeddings e "
            "     WHERE e.content_id = s.content_id "
            "       AND e.image_url = s.first_image_url)) AS failed, "
            "(SELECT max(e.computed_at) FROM spot_embeddings e JOIN spots s "
            "   ON s.content_id = e.content_id AND s.first_image_url = e.image_url) "
            "AS last_computed_at"
        )
    )
    return result.one()


async def embedding_failures_by_reason(session: AsyncSession) -> list[Row[Any]]:
    result = await session.execute(
        text(
            "SELECT f.reason, count(*) AS n FROM embedding_failures f JOIN spots s "
            "ON s.content_id = f.content_id "
            "WHERE s.first_image_url IS NOT NULL AND s.first_image_url <> '' "
            "AND NOT EXISTS (SELECT 1 FROM spot_embeddings e "
            "  WHERE e.content_id = s.content_id AND e.image_url = s.first_image_url) "
            "GROUP BY f.reason ORDER BY f.reason"
        )
    )
    return list(result.all())


async def embedding_recent_window(session: AsyncSession, since: Any) -> Row[Any]:
    result = await session.execute(
        text(
            "SELECT "
            "count(*) FILTER (WHERE first_image_url IS NOT NULL AND first_image_url <> '') "
            "  AS target, "
            "count(*) FILTER (WHERE first_image_url IS NOT NULL AND first_image_url <> '' "
            "  AND EXISTS (SELECT 1 FROM spot_embeddings e WHERE e.content_id = s.content_id "
            "    AND e.image_url = s.first_image_url)) "
            "  AS embedded "
            "FROM spots s WHERE s.synced_at >= :since"
        ),
        {"since": since},
    )
    return result.one()


async def db_ping(session: AsyncSession) -> bool:
    try:
        result = await session.execute(text("SELECT 1"))
        return bool(result.scalar_one() == 1)
    except (SQLAlchemyError, OSError):
        return False


async def user_aggregates(session: AsyncSession) -> Row[Any]:
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


async def list_overseas(
    session: AsyncSession, *, q: str | None, cursor_id: int | None, limit: int
) -> list[Row[Any]]:
    pattern = None
    if q:
        esc = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{esc}%"
    result = await session.execute(
        text(
            "SELECT id, name_ko, country_name_ko, image_url, fame_score, is_hidden "
            "FROM overseas_spots "
            "WHERE (CAST(:pat AS text) IS NULL OR name_ko ILIKE CAST(:pat AS text)) "
            "AND (CAST(:cid AS bigint) IS NULL OR id > CAST(:cid AS bigint)) "
            "ORDER BY id LIMIT :lim"
        ),
        {"pat": pattern, "cid": cursor_id, "lim": limit},
    )
    return list(result.all())


async def set_overseas_hidden(session: AsyncSession, overseas_id: int, hidden: bool) -> bool:
    result = await session.execute(
        text(
            "UPDATE overseas_spots SET is_hidden = :h, updated_at = now() "
            "WHERE id = :oid RETURNING id"
        ),
        {"h": hidden, "oid": overseas_id},
    )
    return result.first() is not None
