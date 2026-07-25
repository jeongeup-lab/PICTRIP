from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text

from app.core.db import AsyncSession
from app.modules.spots.services import attraction_category_sql


@dataclass(frozen=True)
class VectorMatchRow:
    content_id: str
    title: str
    category: str | None
    addr1: str | None
    lat: float | None
    lng: float | None
    image_url: str | None
    cpyrht_div_cd: str | None
    distance: float


_VECTOR_MATCH_SQL = f"""
SELECT spots.content_id,
       spots.title,
       c.lcls_systm3_nm AS category,
       spots.addr1,
       spots.mapy AS lat,
       spots.mapx AS lng,
       spots.first_image_url AS image_url,
       spots.cpyrht_div_cd,
       (se.embedding <=> CAST(:vec AS halfvec(512)))::float AS distance
FROM spot_embeddings se
JOIN spots ON spots.content_id = se.content_id
          AND spots.show_flag = 1
          AND spots.first_image_url IS NOT NULL
          AND spots.first_image_url <> ''
          AND ({attraction_category_sql()})
LEFT JOIN lcls_systm_codes c ON c.lcls_systm3_cd = spots.lcls_systm3
ORDER BY se.embedding <=> CAST(:vec AS halfvec(512))
LIMIT :lim
"""


def _vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{value:.6f}" for value in vector) + "]"


async def match_spots_by_vector(
    session: AsyncSession, vector: list[float], *, limit: int
) -> list[VectorMatchRow]:
    result = await session.execute(
        text(_VECTOR_MATCH_SQL), {"vec": _vector_literal(vector), "lim": limit}
    )
    return [
        VectorMatchRow(
            content_id=row.content_id,
            title=row.title or "",
            category=row.category,
            addr1=row.addr1,
            lat=float(row.lat) if row.lat is not None else None,
            lng=float(row.lng) if row.lng is not None else None,
            image_url=row.image_url,
            cpyrht_div_cd=row.cpyrht_div_cd,
            distance=float(row.distance),
        )
        for row in result
    ]


_CATEGORY_CODE_SQL = """
SELECT lcls_systm3_cd
FROM lcls_systm_codes
WHERE lcls_systm3_nm ILIKE '%' || :kw || '%'
   OR lcls_systm2_nm ILIKE '%' || :kw || '%'
   OR lcls_systm1_nm ILIKE '%' || :kw || '%'
LIMIT :lim
"""


async def find_category_codes(session: AsyncSession, keyword: str, *, limit: int = 40) -> list[str]:
    cleaned = keyword.strip()
    if len(cleaned) < 2:
        return []
    result = await session.execute(text(_CATEGORY_CODE_SQL), {"kw": cleaned, "lim": limit})
    return [row.lcls_systm3_cd for row in result]


@dataclass(frozen=True)
class CandidateRow:
    content_id: str
    title: str
    addr1: str | None
    region_name: str | None
    sigungu_name: str | None
    lat: float | None
    lng: float | None
    image_url: str | None
    cpyrht_div_cd: str | None
    concentration_rate: float | None


_CANDIDATE_SQL = """
SELECT spots.content_id,
       spots.title,
       spots.addr1,
       r.ldong_regn_nm AS region_name,
       g.ldong_signgu_nm AS sigungu_name,
       spots.mapy AS lat,
       spots.mapx AS lng,
       spots.first_image_url AS image_url,
       spots.cpyrht_div_cd,
       sc.concentration_rate
FROM spots
LEFT JOIN regions r ON r.ldong_regn_cd = spots.ldong_regn_cd
LEFT JOIN sigungus g ON g.ldong_signgu_cd = spots.ldong_signgu_cd
LEFT JOIN spot_concentration sc ON sc.content_id = spots.content_id
WHERE spots.show_flag = 1
  AND spots.first_image_url IS NOT NULL
  AND spots.first_image_url <> ''
  AND ({attraction})
  {code_clause}
  {region_clause}
ORDER BY spots.content_id
LIMIT :lim
"""

_CODE_CLAUSE = "AND spots.lcls_systm3 = ANY(CAST(:codes AS text[]))"
_REGION_CLAUSE = "AND spots.addr1 LIKE ANY(CAST(:region_patterns AS text[]))"


async def find_candidates(
    session: AsyncSession,
    *,
    codes: list[str] | None,
    region_prefixes: list[str] | None,
    limit: int,
) -> list[CandidateRow]:
    params: dict[str, object] = {"lim": limit}
    code_clause = ""
    if codes:
        code_clause = _CODE_CLAUSE
        params["codes"] = codes
    region_clause = ""
    if region_prefixes:
        region_clause = _REGION_CLAUSE
        params["region_patterns"] = [f"{prefix}%" for prefix in region_prefixes]
    sql = _CANDIDATE_SQL.format(
        attraction=attraction_category_sql(),
        code_clause=code_clause,
        region_clause=region_clause,
    )
    result = await session.execute(text(sql), params)
    return [
        CandidateRow(
            content_id=row.content_id,
            title=row.title or "",
            addr1=row.addr1,
            region_name=row.region_name,
            sigungu_name=row.sigungu_name,
            lat=float(row.lat) if row.lat is not None else None,
            lng=float(row.lng) if row.lng is not None else None,
            image_url=row.image_url,
            cpyrht_div_cd=row.cpyrht_div_cd,
            concentration_rate=(
                float(row.concentration_rate) if row.concentration_rate is not None else None
            ),
        )
        for row in result
    ]


_TITLE_CANDIDATE_SQL = """
SELECT spots.content_id,
       spots.title,
       spots.addr1,
       r.ldong_regn_nm AS region_name,
       g.ldong_signgu_nm AS sigungu_name,
       spots.mapy AS lat,
       spots.mapx AS lng,
       spots.first_image_url AS image_url,
       spots.cpyrht_div_cd,
       sc.concentration_rate
FROM spots
LEFT JOIN regions r ON r.ldong_regn_cd = spots.ldong_regn_cd
LEFT JOIN sigungus g ON g.ldong_signgu_cd = spots.ldong_signgu_cd
LEFT JOIN spot_concentration sc ON sc.content_id = spots.content_id
WHERE spots.content_id = ANY(CAST(:ids AS text[]))
"""


async def load_candidates_by_ids(
    session: AsyncSession, content_ids: list[str]
) -> dict[str, CandidateRow]:
    if not content_ids:
        return {}
    result = await session.execute(text(_TITLE_CANDIDATE_SQL), {"ids": content_ids})
    return {
        row.content_id: CandidateRow(
            content_id=row.content_id,
            title=row.title or "",
            addr1=row.addr1,
            region_name=row.region_name,
            sigungu_name=row.sigungu_name,
            lat=float(row.lat) if row.lat is not None else None,
            lng=float(row.lng) if row.lng is not None else None,
            image_url=row.image_url,
            cpyrht_div_cd=row.cpyrht_div_cd,
            concentration_rate=(
                float(row.concentration_rate) if row.concentration_rate is not None else None
            ),
        )
        for row in result
    }
