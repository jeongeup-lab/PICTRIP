from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text

from app.core.db import AsyncSession


@dataclass(slots=True)
class SpotSearchRow:
    content_id: str
    title: str
    addr1: str | None
    lat: float | None
    lng: float | None
    image_url: str | None
    cpyrht_div_cd: str | None
    category: str | None
    content_type_id: int
    similarity: float


_SEARCH_SQL = """
    SELECT s.content_id,
           s.title,
           s.addr1,
           s.mapy::float AS lat,
           s.mapx::float AS lng,
           s.first_image_url,
           s.cpyrht_div_cd,
           s.content_type_id,
           c.lcls_systm3_nm AS category,
           word_similarity(:q, s.title) AS sim
    FROM spots s
    LEFT JOIN lcls_systm_codes c ON c.lcls_systm3_cd = s.lcls_systm3
    WHERE s.show_flag = 1
      AND (s.title ILIKE '%' || :q || '%' OR :q <% s.title)
      {region_clause}
    ORDER BY sim DESC,
             {type_boost}
             (regexp_replace(s.title, '\\s*\\(.*\\)$', '') = :q) DESC,
             (s.title ILIKE '%' || :q) DESC,
             length(s.title)
    LIMIT :limit
"""

_REGION_CLAUSE = "AND s.addr1 ILIKE '%' || :region || '%'"

_WORD_SIMILARITY_THRESHOLD_SQL = "SET LOCAL pg_trgm.word_similarity_threshold = 0.4"

MAX_REGION_TOKENS = 100

_REGION_TOKEN_SQL = """
    SELECT DISTINCT r.ldong_regn_nm
    FROM regions r
    LEFT JOIN sigungus g ON g.ldong_regn_cd = r.ldong_regn_cd
    WHERE r.ldong_regn_nm LIKE :tok || '%'
       OR g.ldong_signgu_nm LIKE :tok || '%'
"""


async def search_spots_by_title(
    session: AsyncSession,
    query: str,
    *,
    region_hint: str | None = None,
    preferred_content_types: list[int] | None = None,
    limit: int = 3,
) -> list[SpotSearchRow]:
    clause = _REGION_CLAUSE if region_hint else ""
    if preferred_content_types:
        types_csv = ",".join(str(int(t)) for t in preferred_content_types)
        type_boost = f"(s.content_type_id IN ({types_csv})) DESC,"
    else:
        type_boost = ""
    params: dict[str, object] = {"q": query, "limit": limit}
    if region_hint:
        params["region"] = region_hint
    await session.execute(text(_WORD_SIMILARITY_THRESHOLD_SQL))
    result = await session.execute(
        text(_SEARCH_SQL.format(region_clause=clause, type_boost=type_boost)), params
    )
    return [
        SpotSearchRow(
            content_id=row.content_id,
            title=row.title,
            addr1=row.addr1,
            lat=row.lat,
            lng=row.lng,
            image_url=row.first_image_url,
            cpyrht_div_cd=row.cpyrht_div_cd,
            category=row.category,
            content_type_id=row.content_type_id,
            similarity=float(row.sim),
        )
        for row in result
    ]


async def map_region_tokens_to_sido(session: AsyncSession, tokens: set[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for token in sorted(tokens)[:MAX_REGION_TOKENS]:
        cleaned = token.strip()
        if len(cleaned) < 2:
            continue
        rows = (await session.execute(text(_REGION_TOKEN_SQL), {"tok": cleaned})).all()
        if len(rows) == 1:
            mapping[cleaned] = rows[0].ldong_regn_nm
    return mapping
