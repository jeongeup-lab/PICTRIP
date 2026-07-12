from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

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


_NEIGHBORS_SQL = """
SELECT se.content_id,
       (se.embedding <=> (SELECT embedding FROM overseas_spots WHERE id = :oid))::float AS distance
FROM spot_embeddings se
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
) -> list[tuple[str, float]]:
    result = await session.execute(text(_NEIGHBORS_SQL), {"oid": overseas_id, "lim": limit})
    return [(r.content_id, r.distance) for r in result]


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
