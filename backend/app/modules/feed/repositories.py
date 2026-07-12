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
