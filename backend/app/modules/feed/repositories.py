from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.spots.services import attraction_category_sql

_CATEGORY_SQL = attraction_category_sql()

_KEY_EXPR = (
    "power(greatest("
    "((('x' || left(md5((:seed)::text || wikidata_id), 8))::bit(32)::int)::bigint + 2147483648)"
    " / 4294967296.0, 1e-9), 1.0 / ln(fame_score + 2))"
)

_PAGE_SQL = f"""
WITH scored AS (
    SELECT id, name_ko, country_code, country_name_ko, description_ko,
           image_url, image_author, image_license, image_license_url, image_source_url,
           {_KEY_EXPR} AS shuffle_key
    FROM overseas_spots
    WHERE is_hidden = false
)
SELECT * FROM scored
WHERE ((:cursor_key)::double precision IS NULL)
   OR (shuffle_key, id) < ((:cursor_key)::double precision, (:cursor_id)::bigint)
ORDER BY shuffle_key DESC, id DESC
LIMIT (:lim)::int
"""


@dataclass(frozen=True)
class OverseasPostRow:
    id: int
    name_ko: str
    country_code: str
    country_name_ko: str
    description_ko: str | None
    image_url: str
    image_author: str | None
    image_license: str | None
    image_license_url: str | None
    image_source_url: str
    shuffle_key: float


_NEIGHBORS_SQL = f"""
SELECT se.content_id, se.image_url,
       (se.embedding <=> (SELECT embedding FROM overseas_spots WHERE id = :oid))::float AS distance
FROM spot_embeddings se
JOIN spots ON spots.content_id = se.content_id
          AND spots.first_image_url = se.image_url
          AND spots.show_flag = 1
          AND spots.first_image_url IS NOT NULL
          AND spots.first_image_url <> ''
          AND ({_CATEGORY_SQL})
WHERE EXISTS (
    SELECT 1 FROM overseas_spots o
    WHERE o.id = :oid AND o.is_hidden = false AND o.embedding IS NOT NULL
)
ORDER BY se.embedding <=> (SELECT embedding FROM overseas_spots WHERE id = :oid)
LIMIT :lim
"""


async def get_overseas_brief(session: AsyncSession, overseas_id: int) -> tuple[int, bool] | None:
    row = (
        await session.execute(
            text(
                "SELECT id, embedding IS NOT NULL AS has_embedding FROM overseas_spots "
                "WHERE id = :oid AND is_hidden = false"
            ),
            {"oid": overseas_id},
        )
    ).first()
    return (row.id, row.has_embedding) if row else None


async def find_domestic_neighbors(
    session: AsyncSession, overseas_id: int, *, limit: int
) -> list[tuple[str, str, float]]:
    result = await session.execute(text(_NEIGHBORS_SQL), {"oid": overseas_id, "lim": limit})
    return [(r.content_id, r.image_url, r.distance) for r in result]


async def get_cached_match_state(
    session: AsyncSession, overseas_id: int, content_ids: list[str]
) -> tuple[bool, dict[str, str]] | None:
    rows = (
        await session.execute(
            text(
                "SELECT o.embedding IS NOT NULL AS has_embedding, "
                "current_spot.content_id, current_spot.first_image_url "
                "FROM overseas_spots o "
                "LEFT JOIN LATERAL ("
                "SELECT spots.content_id, spots.first_image_url "
                "FROM spots JOIN spot_embeddings e "
                "ON e.content_id = spots.content_id AND e.image_url = spots.first_image_url "
                "WHERE spots.content_id = ANY(CAST(:content_ids AS text[])) "
                "AND spots.show_flag = 1 AND spots.first_image_url IS NOT NULL "
                "AND spots.first_image_url <> '' "
                f"AND ({_CATEGORY_SQL})"
                ") AS current_spot ON true "
                "WHERE o.id = :oid AND o.is_hidden = false"
            ),
            {"oid": overseas_id, "content_ids": content_ids},
        )
    ).all()
    if not rows:
        return None
    return bool(rows[0].has_embedding), {
        row.content_id: row.first_image_url for row in rows if row.content_id is not None
    }


async def fetch_posts_page(
    session: AsyncSession,
    *,
    seed: str,
    cursor_key: float | None,
    cursor_id: int | None,
    limit: int,
) -> list[OverseasPostRow]:
    result = await session.execute(
        text(_PAGE_SQL),
        {"seed": seed, "cursor_key": cursor_key, "cursor_id": cursor_id or 0, "lim": limit},
    )
    return [OverseasPostRow(**row._mapping) for row in result]
