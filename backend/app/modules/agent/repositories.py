from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from typing import Literal

from sqlalchemy import text

from app.core.db import AsyncSession
from app.modules.spots.services import travel_category_sql

INDOOR_L2 = ("VE06", "VE07")
INDOOR_L3 = ("VE020400", "VE120300")


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


_VECTOR_MATCH_SQL = """
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
          AND ({attraction})
LEFT JOIN lcls_systm_codes c ON c.lcls_systm3_cd = spots.lcls_systm3
WHERE TRUE
  {region_clause}
ORDER BY se.embedding <=> CAST(:vec AS halfvec(512))
LIMIT :lim
"""


def _vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{value:.6f}" for value in vector) + "]"


async def match_spots_by_vector(
    session: AsyncSession,
    vector: list[float],
    *,
    limit: int,
    region_prefixes: list[str] | None = None,
) -> list[VectorMatchRow]:
    params: dict[str, object] = {"vec": _vector_literal(vector), "lim": limit}
    region_clause = ""
    if region_prefixes:
        region_clause = _REGION_CLAUSE
        params["region_patterns"] = [f"{prefix}%" for prefix in region_prefixes]
    sql = _VECTOR_MATCH_SQL.format(attraction=travel_category_sql(), region_clause=region_clause)
    result = await session.execute(text(sql), params)
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


_MOOD_ID_SQL = "SELECT id FROM moods WHERE code = ANY(CAST(:codes AS text[])) ORDER BY id"


async def find_mood_ids(session: AsyncSession, codes: list[str]) -> list[int]:
    if not codes:
        return []
    result = await session.execute(text(_MOOD_ID_SQL), {"codes": codes})
    return [int(row.id) for row in result]


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
    base_ymd: date | None = None
    percentile: int | None = None
    indoor: bool = False
    mood_ids: tuple[int, ...] = ()


CandidateOrder = Literal["id", "rate_asc", "rate_desc", "distance"]

_CANDIDATE_SQL = """
WITH scored AS (
    SELECT spots.content_id,
           spots.title,
           spots.addr1,
           r.ldong_regn_nm AS region_name,
           g.ldong_signgu_nm AS sigungu_name,
           spots.mapy AS lat,
           spots.mapx AS lng,
           spots.first_image_url AS image_url,
           spots.cpyrht_div_cd,
           sc.concentration_rate,
           sc.base_ymd,
           COALESCE(spots.lcls_systm2 = ANY(CAST(:indoor_l2 AS text[]))
                    OR spots.lcls_systm3 = ANY(CAST(:indoor_l3 AS text[])), FALSE) AS indoor,
           {percentile} AS percentile
    FROM spots
    LEFT JOIN regions r ON r.ldong_regn_cd = spots.ldong_regn_cd
    LEFT JOIN sigungus g ON g.ldong_signgu_cd = spots.ldong_signgu_cd
    {concentration_join} spot_concentration sc ON sc.content_id = spots.content_id
    WHERE spots.show_flag = 1
      AND spots.first_image_url IS NOT NULL
      AND spots.first_image_url <> ''
      AND ({attraction})
      {code_clause}
      {region_clause}
      {indoor_clause}
      {mood_clause}
      {locatable_clause}
)
SELECT * FROM scored
WHERE TRUE
  {percentile_clause}
ORDER BY {order}
LIMIT :lim
"""

_CODE_CLAUSE = "AND spots.lcls_systm3 = ANY(CAST(:codes AS text[]))"
_REGION_CLAUSE = "AND spots.addr1 LIKE ANY(CAST(:region_patterns AS text[]))"
_LOCATABLE_CLAUSE = "AND spots.mapx IS NOT NULL AND spots.mapy IS NOT NULL"
_INDOOR_CLAUSE = (
    "AND (spots.lcls_systm2 = ANY(CAST(:indoor_l2 AS text[])) "
    "OR spots.lcls_systm3 = ANY(CAST(:indoor_l3 AS text[])))"
)
_MOOD_CLAUSE = (
    "AND EXISTS (SELECT 1 FROM spot_moods sm "
    "WHERE sm.content_id = spots.content_id "
    "AND sm.mood_id = ANY(CAST(:mood_ids AS int[])))"
)
_CEILING_CLAUSE = "AND percentile <= :ceiling"
_FLOOR_CLAUSE = "AND percentile >= :floor"
_PERCENTILE_EXPR = (
    "round(greatest(1.0, cume_dist() OVER (ORDER BY sc.concentration_rate) * 100))::int"
)
_DISTANCE_ORDER = (
    "power(lat - CAST(:lat AS numeric), 2) "
    "+ power((lng - CAST(:lng AS numeric)) * CAST(:lng_scale AS numeric), 2)"
)
_ORDER_BY: dict[CandidateOrder, str] = {
    "id": "content_id",
    "rate_asc": "concentration_rate ASC, content_id",
    "rate_desc": "concentration_rate DESC, content_id",
    "distance": f"{_DISTANCE_ORDER}, content_id",
}


async def find_candidates(
    session: AsyncSession,
    *,
    codes: list[str] | None,
    region_prefixes: list[str] | None,
    limit: int,
    order: CandidateOrder = "id",
    rated_only: bool = False,
    percentile_ceiling: int | None = None,
    percentile_floor: int | None = None,
    lat: float | None = None,
    lng: float | None = None,
    indoor_only: bool = False,
    mood_ids: list[int] | None = None,
) -> list[CandidateRow]:
    params: dict[str, object] = {"lim": limit}
    percentile_clause = ""
    if rated_only and percentile_ceiling is not None:
        percentile_clause = _CEILING_CLAUSE
        params["ceiling"] = percentile_ceiling
    elif rated_only and percentile_floor is not None:
        percentile_clause = _FLOOR_CLAUSE
        params["floor"] = percentile_floor
    code_clause = ""
    if codes:
        code_clause = _CODE_CLAUSE
        params["codes"] = codes
    region_clause = ""
    if region_prefixes:
        region_clause = _REGION_CLAUSE
        params["region_patterns"] = [f"{prefix}%" for prefix in region_prefixes]
    params["indoor_l2"] = list(INDOOR_L2)
    params["indoor_l3"] = list(INDOOR_L3)
    indoor_clause = _INDOOR_CLAUSE if indoor_only else ""
    mood_clause = ""
    if mood_ids:
        mood_clause = _MOOD_CLAUSE
        params["mood_ids"] = mood_ids
    if order == "distance":
        if lat is None or lng is None:
            raise ValueError("distance order requires lat/lng")
        params["lat"] = lat
        params["lng"] = lng
        params["lng_scale"] = math.cos(math.radians(lat))
    sql = _CANDIDATE_SQL.format(
        attraction=travel_category_sql(),
        code_clause=code_clause,
        region_clause=region_clause,
        indoor_clause=indoor_clause,
        mood_clause=mood_clause,
        locatable_clause=_LOCATABLE_CLAUSE if order == "distance" else "",
        concentration_join="JOIN" if rated_only else "LEFT JOIN",
        percentile=_PERCENTILE_EXPR if rated_only else "NULL",
        percentile_clause=percentile_clause,
        order=_ORDER_BY[order],
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
            base_ymd=row.base_ymd,
            percentile=int(row.percentile) if row.percentile is not None else None,
            indoor=bool(row.indoor),
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
       sc.concentration_rate,
       COALESCE(spots.lcls_systm2 = ANY(CAST(:indoor_l2 AS text[]))
                OR spots.lcls_systm3 = ANY(CAST(:indoor_l3 AS text[])), FALSE) AS indoor,
       ARRAY(
           SELECT sm.mood_id FROM spot_moods sm WHERE sm.content_id = spots.content_id
       ) AS mood_ids
FROM spots
LEFT JOIN regions r ON r.ldong_regn_cd = spots.ldong_regn_cd
LEFT JOIN sigungus g ON g.ldong_signgu_cd = spots.ldong_signgu_cd
LEFT JOIN spot_concentration sc ON sc.content_id = spots.content_id
WHERE spots.content_id = ANY(CAST(:ids AS text[]))
  AND spots.show_flag = 1
  AND spots.first_image_url IS NOT NULL
  AND spots.first_image_url <> ''
"""


_RATED_IDS_SQL = """
SELECT content_id FROM spot_concentration WHERE content_id = ANY(CAST(:ids AS text[]))
"""


async def find_rated_content_ids(session: AsyncSession, content_ids: list[str]) -> set[str]:
    if not content_ids:
        return set()
    result = await session.execute(text(_RATED_IDS_SQL), {"ids": content_ids})
    return {row.content_id for row in result}


async def load_candidates_by_ids(
    session: AsyncSession, content_ids: list[str]
) -> dict[str, CandidateRow]:
    if not content_ids:
        return {}
    result = await session.execute(
        text(_TITLE_CANDIDATE_SQL),
        {"ids": content_ids, "indoor_l2": list(INDOOR_L2), "indoor_l3": list(INDOOR_L3)},
    )
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
            indoor=bool(row.indoor),
            mood_ids=tuple(int(mood_id) for mood_id in row.mood_ids),
        )
        for row in result
    }


_OVERVIEW_SQL = """
SELECT content_id, overview
FROM spot_details
WHERE content_id = ANY(CAST(:ids AS text[]))
  AND overview IS NOT NULL
  AND overview <> ''
"""


async def load_overviews(session: AsyncSession, content_ids: list[str]) -> dict[str, str]:
    if not content_ids:
        return {}
    rows = await session.execute(text(_OVERVIEW_SQL), {"ids": content_ids})
    return {row.content_id: row.overview for row in rows}
