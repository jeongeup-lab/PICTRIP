"""Mood / region catalog reads + free-text search + seeded daily pick."""

from __future__ import annotations

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ResourceNotFound
from app.modules.spots.models import Mood, Region
from app.modules.spots.services.nearby import derive_category
from app.modules.spots.services.region import _validate_region
from app.modules.spots.services.rows import SpotCardRow

_MAX_MOOD_SPOTS = 10_000
_MAX_SEARCH_RESULTS = 50
_MAX_REGION_SPOTS = 60


async def list_moods(session: AsyncSession) -> list[Mood]:
    result = await session.execute(select(Mood).order_by(Mood.sort_order))
    return list(result.scalars().all())


async def count_spots_per_mood(session: AsyncSession) -> dict[int, int]:
    """``{mood_id: spot_count}`` for the mood cover cards (#6 무드 탭 "N곳").

    Counts exactly the spots ``list_spots_by_mood`` would surface — active,
    image-bearing spots tagged with the mood — so the cover count matches what
    the user sees when they open the collection. One GROUP BY over the indexed
    ``spot_moods.mood_id`` join (idx_spot_moods_mood), so all 8 moods cost a
    single cheap query.
    """
    sql = text(
        """
        SELECT sm.mood_id AS mood_id, COUNT(*) AS n
        FROM spot_moods sm
        JOIN spots s ON s.content_id = sm.content_id
        WHERE s.show_flag = 1
          AND s.first_image_url IS NOT NULL
        GROUP BY sm.mood_id
        """
    )
    result = await session.execute(sql)
    return {row.mood_id: row.n for row in result}


async def list_regions(session: AsyncSession) -> list[Region]:
    """The 17 sido (province) reference rows, ordered by sido code
    (Seoul 11 → Jeonbuk 52)."""
    result = await session.execute(select(Region).order_by(Region.ldong_regn_cd))
    return list(result.scalars().all())


async def list_spots_by_mood(
    session: AsyncSession,
    mood_code: str,
    *,
    limit: int = 8,
    region: str | None = None,
) -> list[SpotCardRow]:
    """Return up to `limit` randomly-sampled spots tagged with the given mood.

    Filters: show_flag=1, first_image_url IS NOT NULL, and optionally a sido
    (province) region (areacode). Raises ResourceNotFound if the mood code is
    unknown, and
    ValidationFailed if a non-empty `region` is not a real areacode.
    """
    limit = max(1, min(limit, _MAX_MOOD_SPOTS))
    mood = await session.scalar(select(Mood).where(Mood.code == mood_code))
    if mood is None:
        raise ResourceNotFound(f"Mood '{mood_code}' not found.")

    region_code = await _validate_region(session, region)

    region_filter = "AND s.ldong_regn_cd = :region" if region_code else ""
    sql = text(
        f"""
        SELECT s.content_id, s.title, s.first_image_url, s.addr1,
               s.mapx::float AS mapx, s.mapy::float AS mapy
        FROM spots s
        JOIN spot_moods sm ON sm.content_id = s.content_id
        WHERE sm.mood_id = :mood_id
          AND s.show_flag = 1
          AND s.first_image_url IS NOT NULL
          {region_filter}
        ORDER BY random()
        LIMIT :lim
        """
    )
    params: dict[str, object] = {"mood_id": mood.id, "lim": limit}
    if region_code:
        params["region"] = region_code
    result = await session.execute(sql, params)
    return [
        SpotCardRow(
            content_id=row.content_id,
            title=row.title,
            first_image_url=row.first_image_url,
            addr1=row.addr1,
            mapx=row.mapx,
            mapy=row.mapy,
        )
        for row in result
    ]


def _escape_like(value: str) -> str:
    """Escape LIKE/ILIKE wildcards so user input is matched literally.

    A literal ``%`` or ``_`` typed by the user must not act as a wildcard; the
    backslash is the ESCAPE char declared in the query.
    """
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def search_spots(
    session: AsyncSession,
    query: str,
    *,
    limit: int = 20,
    region: str | None = None,
) -> list[SpotCardRow]:
    """Free-text search over active spots by place name (title / addr1).

    Case-insensitive substring match (ILIKE) on title OR addr1, filtered to
    show_flag=1 and optionally a sido (province) region. Results are
    prefix-boosted (titles that start with the query come first) then ordered by
    title. A blank query returns ``[]``. Raises ValidationFailed for an unknown
    region code (mirrors ``list_spots_by_mood``). Korean chosung (initial-jamo
    prefix) search is out of scope.

    The ``spots.title`` / ``spots.addr1`` columns carry a pg_trgm GIN index
    (``WHERE show_flag = 1``) so the substring ILIKE is index-assisted rather
    than a sequential scan (migration 0008).
    """
    q = query.strip()
    if not q:
        return []
    limit = max(1, min(limit, _MAX_SEARCH_RESULTS))

    region_code = await _validate_region(session, region)

    region_filter = "AND s.ldong_regn_cd = :region" if region_code else ""
    escaped = _escape_like(q)
    sql = text(
        f"""
        SELECT s.content_id, s.title, s.first_image_url, s.addr1,
               s.mapx::float AS mapx, s.mapy::float AS mapy
        FROM spots s
        WHERE s.show_flag = 1
          AND (s.title ILIKE :like ESCAPE '\\' OR s.addr1 ILIKE :like ESCAPE '\\')
          {region_filter}
        ORDER BY (s.title ILIKE :prefix ESCAPE '\\') DESC, s.title ASC
        LIMIT :lim
        """
    )
    params: dict[str, object] = {
        "like": f"%{escaped}%",
        "prefix": f"{escaped}%",
        "lim": limit,
    }
    if region_code:
        params["region"] = region_code
    result = await session.execute(sql, params)
    return [
        SpotCardRow(
            content_id=row.content_id,
            title=row.title,
            first_image_url=row.first_image_url,
            addr1=row.addr1,
            mapx=row.mapx,
            mapy=row.mapy,
        )
        for row in result
    ]


async def pick_active_spot_by_seed(
    session: AsyncSession,
    seed: int,
) -> SpotCardRow | None:
    """Deterministically pick one active, image-bearing spot for `seed`.

    Pool: show_flag=1 AND first_image_url IS NOT NULL AND first_image_url <> ''.
    Ordered by content_id (stable, PK-backed); returns the spot at
    OFFSET (seed % count). Returns None if the pool is empty.
    """
    count = await session.scalar(
        text(
            "SELECT count(*) FROM spots "
            "WHERE show_flag = 1 "
            "AND first_image_url IS NOT NULL "
            "AND first_image_url <> ''"
        )
    )
    if not count:
        return None

    sql = text(
        """
        SELECT s.content_id, s.title, s.first_image_url, s.addr1,
               s.mapx::float AS mapx, s.mapy::float AS mapy
        FROM spots s
        WHERE s.show_flag = 1
          AND s.first_image_url IS NOT NULL
          AND s.first_image_url <> ''
        ORDER BY s.content_id
        OFFSET :off
        LIMIT 1
        """
    )
    row = (await session.execute(sql, {"off": seed % count})).first()
    if row is None:
        return None
    return SpotCardRow(
        content_id=row.content_id,
        title=row.title,
        first_image_url=row.first_image_url,
        addr1=row.addr1,
        mapx=row.mapx,
        mapy=row.mapy,
    )


async def list_spots_by_region(
    session: AsyncSession,
    *,
    signgu_codes: list[str],
    regn_codes: list[str],
    limit: int = 24,
) -> list[SpotCardRow]:
    """Image-bearing active spots in the given regions, ordered by KTO 집중률 desc.

    `signgu_codes` match `spots.ldong_signgu_cd` (시군구), `regn_codes` match
    `spots.ldong_regn_cd` (시도); the two sets are OR'd (union). At least one
    list must be non-empty (the route enforces this). Spots with a 집중률 row
    sort first (rate desc); the rest follow by title — a deterministic order so
    the same region always yields the same lead card (used as the curation
    cover). Only `show_flag=1` rows with a non-empty `first_image_url`.
    """
    limit = max(1, min(limit, _MAX_REGION_SPOTS))
    if not signgu_codes and not regn_codes:
        return []

    clauses: list[str] = []
    params: dict[str, object] = {"lim": limit}
    if signgu_codes:
        clauses.append("s.ldong_signgu_cd = ANY(:signgu)")
        params["signgu"] = signgu_codes
    if regn_codes:
        clauses.append("s.ldong_regn_cd = ANY(:regn)")
        params["regn"] = regn_codes
    region_filter = " OR ".join(clauses)

    sql = text(
        f"""
        SELECT s.content_id, s.title, s.first_image_url, s.addr1,
               s.mapx::float AS mapx, s.mapy::float AS mapy,
               s.lcls_systm1 AS l1, s.lcls_systm2 AS l2, s.lcls_systm3 AS l3,
               sc.concentration_rate::float AS rate
        FROM spots s
        LEFT JOIN spot_concentration sc ON sc.content_id = s.content_id
        WHERE s.show_flag = 1
          AND s.first_image_url IS NOT NULL
          AND s.first_image_url <> ''
          AND ({region_filter})
        ORDER BY sc.concentration_rate DESC NULLS LAST, s.title ASC, s.content_id ASC
        LIMIT :lim
        """
    )
    result = await session.execute(sql, params)
    return [
        SpotCardRow(
            content_id=row.content_id,
            title=row.title,
            first_image_url=row.first_image_url,
            addr1=row.addr1,
            mapx=row.mapx,
            mapy=row.mapy,
            category=derive_category(row.l1, row.l2, row.l3),
        )
        for row in result
    ]
