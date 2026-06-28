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

from sqlalchemy import Row, delete, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

# The admin module's own ORM-mapped surfaces: admin_users (console credentials,
# DB-backed auth A01 §1.3) and curations/curation_spots (the curation editor's
# scoped write surface, A01 §7). CLAUDE.md grants admin scoped ownership of these,
# so importing the models here is sanctioned (ORM over raw SQL for writes: clearer
# column binding, CHECK/FK violations surface as SQLAlchemy errors). All OTHER
# admin access stays read-only raw SQL.
from app.modules.admin.models import AdminUser
from app.modules.spots.models import Curation, CurationSpot


async def get_admin_user(session: AsyncSession, username: str) -> AdminUser | None:
    """The admin-console login for ``username`` (None if absent). Read-only."""
    return (
        await session.execute(select(AdminUser).where(AdminUser.username == username))
    ).scalar_one_or_none()


async def count_spots(session: AsyncSession) -> int:
    result = await session.execute(text("SELECT count(*) FROM spots"))
    return int(result.scalar_one())


async def count_embeddings(session: AsyncSession) -> int:
    """Spots with a CLIP embedding (spot_embeddings is the vector store)."""
    result = await session.execute(text("SELECT count(*) FROM spot_embeddings"))
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


# --- curation editor (A01 §7 / ADM-012~015) -----------------------------------
# Reads return raw Rows; writes operate on the passed session (services own the
# commit/transaction boundary, A01 §1.1). Curation/CurationSpot are admin-owned.


async def list_curations(session: AsyncSession) -> list[Row[Any]]:
    """All curations + resolved cover image, grouped/ordered by the service.

    Ordered (type, position) so the service can split into heroes/rails/editorial
    while preserving per-group position order in a single query.
    """
    result = await session.execute(
        text(
            "SELECT c.id, c.type, c.slug, c.title, c.subtitle, c.is_published, c.position, "
            "s.first_image_url AS cover_url "
            "FROM curations c "
            "LEFT JOIN spots s ON s.content_id = c.cover_spot_id "
            "ORDER BY c.type, c.position, c.id"
        )
    )
    return list(result.all())


async def get_curation(session: AsyncSession, curation_id: int) -> Curation | None:
    return (
        await session.execute(select(Curation).where(Curation.id == curation_id))
    ).scalar_one_or_none()


async def get_cover_spot(session: AsyncSession, content_id: str) -> Row[Any] | None:
    """Cover spot projection (name/image) for the detail payload."""
    result = await session.execute(
        text("SELECT content_id, title, first_image_url FROM spots WHERE content_id = :cid"),
        {"cid": content_id},
    )
    return result.first()


async def curation_handpicks(session: AsyncSession, curation_id: int) -> list[Row[Any]]:
    """Handpicked spots (curation_spots) joined to spots, ordered by position.

    ``category`` mirrors the canonical card category (lcls_systm_codes.lcls_systm3_nm).
    """
    result = await session.execute(
        text(
            "SELECT cs.content_id, cs.position, s.title, s.first_image_url, "
            "lc.lcls_systm3_nm AS category "
            "FROM curation_spots cs "
            "JOIN spots s ON s.content_id = cs.content_id "
            "LEFT JOIN lcls_systm_codes lc ON lc.lcls_systm3_cd = s.lcls_systm3 "
            "WHERE cs.curation_id = :cid ORDER BY cs.position"
        ),
        {"cid": curation_id},
    )
    return list(result.all())


async def spot_exposable_with_image(session: AsyncSession, content_id: str) -> bool:
    """True iff the spot exists, is exposable (show_flag=1) AND has an image.

    Cover validation per A01 §7 ("표지 없으면 거부").
    """
    result = await session.execute(
        text(
            "SELECT 1 FROM spots "
            "WHERE content_id = :cid AND show_flag = 1 AND first_image_url IS NOT NULL"
        ),
        {"cid": content_id},
    )
    return result.first() is not None


async def existing_spot_ids(session: AsyncSession, content_ids: list[str]) -> set[str]:
    """Subset of ``content_ids`` that exist in spots (any show_flag)."""
    if not content_ids:
        return set()
    result = await session.execute(
        text("SELECT content_id FROM spots WHERE content_id = ANY(:ids)"),
        {"ids": content_ids},
    )
    return {r.content_id for r in result.all()}


async def update_curation_fields(
    session: AsyncSession,
    curation: Curation,
    *,
    title: str,
    subtitle: str | None,
    lead: str | None,
    intro: str | None,
    cover_spot_id: str | None,
    is_published: bool,
    position: int,
) -> None:
    """Mutate the editable columns + bump updated_at (no auto-onupdate, A01 §7).

    Operates on the passed (managed) ORM instance; the service commits.
    """
    from datetime import UTC, datetime

    curation.title = title
    curation.subtitle = subtitle
    curation.lead = lead
    curation.intro = intro
    curation.cover_spot_id = cover_spot_id
    curation.is_published = is_published
    curation.position = position
    curation.updated_at = datetime.now(tz=UTC)


async def replace_curation_spots(
    session: AsyncSession, curation_id: int, spot_ids: list[str]
) -> None:
    """Delete-all-then-insert handpicks for one curation (position = index).

    Empty ``spot_ids`` just clears (curation reverts to the quality-pool auto-fill).
    """
    await session.execute(delete(CurationSpot).where(CurationSpot.curation_id == curation_id))
    if spot_ids:
        session.add_all(
            [
                CurationSpot(curation_id=curation_id, content_id=cid, position=i)
                for i, cid in enumerate(spot_ids)
            ]
        )
    await session.flush()


async def admin_spot_search(
    session: AsyncSession, q: str, region: str | None, limit: int
) -> list[Row[Any]]:
    """Admin-only trgm ILIKE picker over title/addr1, scoped show_flag=1.

    Uses idx_spots_title_trgm / idx_spots_addr1_trgm (partial WHERE show_flag=1).
    Minimal fields; ordered by title.
    """
    sql = (
        "SELECT s.content_id, s.title, s.ldong_regn_cd, r.ldong_regn_nm AS region_name, "
        "s.first_image_url "
        "FROM spots s "
        "LEFT JOIN regions r ON r.ldong_regn_cd = s.ldong_regn_cd "
        "WHERE s.show_flag = 1 AND (s.title ILIKE :pat OR s.addr1 ILIKE :pat)"
    )
    params: dict[str, Any] = {"pat": f"%{q}%", "limit": limit}
    if region:
        sql += " AND s.ldong_regn_cd = :region"
        params["region"] = region
    sql += " ORDER BY s.title LIMIT :limit"
    result = await session.execute(text(sql), params)
    return list(result.all())
