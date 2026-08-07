from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from os.path import commonprefix
from typing import Any

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
        lookup = canonical_region_token(cleaned)
        rows = (await session.execute(text(_REGION_TOKEN_SQL), {"tok": lookup})).all()
        if len(rows) == 1:
            mapping[cleaned] = rows[0].ldong_regn_nm
    return mapping


@dataclass(frozen=True, slots=True)
class RegionPrefix:
    prefix: str
    sido: str

    @property
    def narrowed(self) -> bool:
        return self.prefix != self.sido


_MIN_MERGED_CHARS = 2
_SIDO_TIER = 1
_SIGUNGU_TIER = 2

SIDO_SPELLINGS: dict[str, str] = {
    "충북": "충청북",
    "충남": "충청남",
    "경북": "경상북",
    "경남": "경상남",
    "전남": "전라남",
    "강원도": "강원",
    "제주도": "제주",
    "전라북도": "전북",
    "서울시": "서울",
    "부산시": "부산",
    "대구시": "대구",
    "인천시": "인천",
    "대전시": "대전",
    "울산시": "울산",
    "세종시": "세종",
}


def canonical_region_token(token: str) -> str:
    return SIDO_SPELLINGS.get(token, token)


_REGION_PREFIX_SQL = """
    SELECT r.ldong_regn_nm AS sido, CAST(NULL AS varchar) AS sigungu, 1 AS tier
    FROM regions r
    WHERE r.ldong_regn_nm LIKE :tok || '%'
    UNION
    SELECT r.ldong_regn_nm AS sido, g.ldong_signgu_nm AS sigungu, 2 AS tier
    FROM sigungus g
    JOIN regions r ON r.ldong_regn_cd = g.ldong_regn_cd
    WHERE g.ldong_signgu_nm LIKE :tok || '%'
"""


async def map_region_tokens_to_prefixes(
    session: AsyncSession, tokens: set[str]
) -> dict[str, RegionPrefix]:
    mapping: dict[str, RegionPrefix] = {}
    for token in sorted(tokens)[:MAX_REGION_TOKENS]:
        cleaned = token.strip()
        if len(cleaned) < 2:
            continue
        lookup = canonical_region_token(cleaned)
        rows = (await session.execute(text(_REGION_PREFIX_SQL), {"tok": lookup})).all()
        if (resolved := _pick_region_prefix(rows)) is not None:
            mapping[cleaned] = resolved
    return mapping


def _pick_region_prefix(rows: Sequence[Any]) -> RegionPrefix | None:
    sido_rows = [row for row in rows if row.tier == _SIDO_TIER]
    if sido_rows:
        if len(sido_rows) > 1:
            return None
        sido = sido_rows[0].sido
        return RegionPrefix(prefix=sido, sido=sido)
    sigungu_rows = [row for row in rows if row.tier == _SIGUNGU_TIER]
    if not sigungu_rows:
        return None
    if len(sigungu_rows) == 1:
        row = sigungu_rows[0]
        return RegionPrefix(prefix=f"{row.sido} {row.sigungu}", sido=row.sido)
    return _merged_districts(sigungu_rows)


def _merged_districts(rows: Sequence[Any]) -> RegionPrefix | None:
    """전주시완산구·전주시덕진구처럼 한 시가 구로 쪼개진 경우만 묶는다."""
    sidos = {row.sido for row in rows}
    if len(sidos) != 1:
        return None
    shared = commonprefix([row.sigungu for row in rows]).strip()
    if len(shared) < _MIN_MERGED_CHARS:
        return None
    sido = sidos.pop()
    return RegionPrefix(prefix=f"{sido} {shared}", sido=sido)
