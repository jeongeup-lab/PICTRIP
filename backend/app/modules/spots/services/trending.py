"""전국 "집중률 TOP" read — KTO 관광지 집중률 ranking (ADR-0016).

Reads the ``spot_concentration`` table (populated by
``scripts/sync_concentration.py``) joined to active, image-bearing spots,
ordered by KTO 집중률 descending. The rate is KTO's published metric verbatim, so
the ranking is real (no fabricated "인기" order). Spots with no 집중률 row are
absent from the source table and therefore excluded from this tab by construction.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.spots.services.region import _validate_region
from app.modules.spots.services.rows import TrendingSpotRow

_MAX_TRENDING = 100


async def list_trending(
    session: AsyncSession,
    *,
    limit: int = 10,
    region: str | None = None,
) -> list[TrendingSpotRow]:
    """Top spots by KTO 집중률, descending.

    Filters to ``show_flag = 1`` and a present ``first_image_url`` (so every card
    has an image), and optionally a sido (province) region. ``rank`` is 1-based
    over the returned slice. Raises ValidationFailed for an unknown region code
    (mirrors ``list_spots_by_mood`` / ``search_spots``).
    """
    limit = max(1, min(limit, _MAX_TRENDING))

    region_code = await _validate_region(session, region)

    region_filter = "AND s.ldong_regn_cd = :region" if region_code else ""
    sql = text(
        f"""
        SELECT s.content_id, s.title, s.first_image_url, s.addr1,
               s.mapx::float AS mapx, s.mapy::float AS mapy,
               r.ldong_regn_nm AS region_name,
               sc.concentration_rate::float AS rate
        FROM spot_concentration sc
        JOIN spots s ON s.content_id = sc.content_id
        LEFT JOIN regions r ON r.ldong_regn_cd = s.ldong_regn_cd
        WHERE s.show_flag = 1
          AND s.first_image_url IS NOT NULL
          {region_filter}
        ORDER BY sc.concentration_rate DESC, s.content_id ASC
        LIMIT :lim
        """
    )
    params: dict[str, object] = {"lim": limit}
    if region_code:
        params["region"] = region_code
    result = await session.execute(sql, params)
    return [
        TrendingSpotRow(
            content_id=row.content_id,
            title=row.title,
            first_image_url=row.first_image_url,
            addr1=row.addr1,
            mapx=row.mapx,
            mapy=row.mapy,
            region_name=row.region_name,
            concentration_rate=row.rate,
            rank=i,
        )
        for i, row in enumerate(result, start=1)
    ]
