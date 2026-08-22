from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.spots.categories import (
    NearbyCategory,
    all_categories_sql,
    attraction_category_sql,
    category_sql,
    travel_category_sql,
)

_CATEGORY_SQL = attraction_category_sql()
_ALL_CATEGORIES_SQL = all_categories_sql()

_KEY_EXPR = (
    "power(greatest("
    "((('x' || left(md5((:seed)::text || wikidata_id), 8))::bit(32)::int)::bigint + 2147483648)"
    " / 4294967296.0, 1e-9), 1.0 / ln(fame_score + 2))"
)

_LIVE_MATCH_JOIN_SQL = f"""
    JOIN spots ON spots.content_id = m.content_id
              AND spots.show_flag = 1
              AND spots.first_image_url IS NOT NULL
              AND spots.first_image_url <> ''
              AND ({_CATEGORY_SQL})
    JOIN spot_embeddings e ON e.content_id = spots.content_id
                          AND e.image_url = spots.first_image_url
"""

_PAGE_SQL = f"""
WITH scored AS (
    SELECT id, name_ko, country_code, country_name_ko, description_ko,
           image_url, image_author, image_license, image_license_url, image_source_url,
           {_KEY_EXPR} AS shuffle_key
    FROM overseas_spots
    WHERE is_hidden = false
      AND embedding IS NOT NULL
      AND (
          NOT EXISTS (SELECT 1 FROM overseas_spot_matches)
          OR (
              SELECT count(*) FROM overseas_spot_matches m
              {_LIVE_MATCH_JOIN_SQL}
              WHERE m.overseas_id = overseas_spots.id
          ) >= 3
      )
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
WITH single AS (
    SELECT se.content_id, se.image_url,
           (se.embedding <=> (SELECT embedding FROM overseas_spots WHERE id = :oid))::float
               AS distance
    FROM spot_embeddings se
    JOIN spots ON spots.content_id = se.content_id
              AND spots.first_image_url = se.image_url
              AND spots.show_flag = 1
              AND spots.first_image_url IS NOT NULL
              AND spots.first_image_url <> ''
              AND ({_CATEGORY_SQL})
    ORDER BY se.embedding <=> (SELECT embedding FROM overseas_spots WHERE id = :oid)
    LIMIT :lim
), gallery AS (
    SELECT ge.content_id, ge.image_url,
           (ge.embedding <=> (SELECT embedding FROM overseas_spots WHERE id = :oid))::float
               AS distance
    FROM spot_embeddings_gallery ge
    JOIN spots ON spots.content_id = ge.content_id
              AND spots.first_image_url = ge.image_url
              AND spots.show_flag = 1
              AND spots.first_image_url IS NOT NULL
              AND spots.first_image_url <> ''
              AND ({_CATEGORY_SQL})
    ORDER BY ge.embedding <=> (SELECT embedding FROM overseas_spots WHERE id = :oid)
    LIMIT :lim
)
SELECT content_id, image_url, distance
FROM (
    SELECT DISTINCT ON (content_id) content_id, image_url, distance
    FROM (SELECT * FROM single UNION ALL SELECT * FROM gallery) candidates
    ORDER BY content_id, distance
) best
WHERE EXISTS (
    SELECT 1 FROM overseas_spots o
    WHERE o.id = :oid AND o.embedding IS NOT NULL
)
ORDER BY distance
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


@dataclass(frozen=True)
class MatchRow:
    overseas_id: int
    content_id: str
    title: str
    region_label: str
    image_url: str
    overview: str | None
    cpyrht_div_cd: str | None


_MATCHES_SQL = f"""
SELECT m.overseas_id,
       spots.content_id,
       spots.title,
       spots.first_image_url,
       spots.cpyrht_div_cd,
       r.ldong_regn_nm AS region_name,
       sg.ldong_signgu_nm AS sigungu_name,
       sd.overview AS overview
FROM overseas_spot_matches m
JOIN spots ON spots.content_id = m.content_id
          AND spots.show_flag = 1
          AND spots.first_image_url IS NOT NULL
          AND spots.first_image_url <> ''
          AND ({_CATEGORY_SQL})
JOIN spot_embeddings e ON e.content_id = spots.content_id
                      AND e.image_url = spots.first_image_url
LEFT JOIN regions r ON r.ldong_regn_cd = spots.ldong_regn_cd
LEFT JOIN sigungus sg ON sg.ldong_signgu_cd = spots.ldong_signgu_cd
LEFT JOIN spot_details sd ON sd.content_id = spots.content_id
WHERE m.overseas_id = ANY(CAST(:oids AS bigint[]))
ORDER BY m.overseas_id, m.rank
"""


async def load_matches(session: AsyncSession, overseas_ids: list[int]) -> dict[int, list[MatchRow]]:
    """spot_embeddings 조인이 신선도 검증을 겸한다 — 이미지가 바뀐 스팟은 여기서 빠진다."""
    if not overseas_ids:
        return {}
    result = await session.execute(text(_MATCHES_SQL), {"oids": overseas_ids})
    grouped: dict[int, list[MatchRow]] = {oid: [] for oid in overseas_ids}
    for row in result:
        grouped[row.overseas_id].append(
            MatchRow(
                overseas_id=row.overseas_id,
                content_id=row.content_id,
                title=row.title or "",
                region_label=" ".join(part for part in (row.region_name, row.sigungu_name) if part),
                image_url=row.first_image_url,
                overview=row.overview,
                cpyrht_div_cd=row.cpyrht_div_cd,
            )
        )
    return grouped


_REBUILD_SQL = f"""
INSERT INTO overseas_spot_matches (overseas_id, rank, content_id, distance)
SELECT o.id, ranked.rank, ranked.content_id, ranked.distance
FROM overseas_spots o
CROSS JOIN LATERAL (
    SELECT content_id, distance,
           row_number() OVER (ORDER BY distance, content_id) AS rank
    FROM (
        SELECT DISTINCT ON (content_id) content_id, distance
        FROM (
            (SELECT se.content_id, (se.embedding <=> o.embedding)::float AS distance
             FROM spot_embeddings se
             JOIN spots ON spots.content_id = se.content_id
                       AND spots.first_image_url = se.image_url
                       AND spots.show_flag = 1
                       AND spots.first_image_url IS NOT NULL
                       AND spots.first_image_url <> ''
                       AND ({_CATEGORY_SQL})
             ORDER BY se.embedding <=> o.embedding
             LIMIT (:candidates)::int)
            UNION ALL
            (SELECT ge.content_id, (ge.embedding <=> o.embedding)::float
             FROM spot_embeddings_gallery ge
             JOIN spots ON spots.content_id = ge.content_id
                       AND spots.first_image_url = ge.image_url
                       AND spots.show_flag = 1
                       AND spots.first_image_url IS NOT NULL
                       AND spots.first_image_url <> ''
                       AND ({_CATEGORY_SQL})
             ORDER BY ge.embedding <=> o.embedding
             LIMIT (:candidates)::int)
        ) candidates
        ORDER BY content_id, distance
    ) deduped
    WHERE distance <= (:distance_max)::double precision
    ORDER BY distance, content_id
    LIMIT 3
) ranked
WHERE o.embedding IS NOT NULL
"""


async def rebuild_matches(
    session: AsyncSession, *, candidates: int, distance_max: float
) -> dict[str, int]:
    """DELETE + INSERT 를 한 트랜잭션에 묶는다 — 중간 상태가 보이면 피드가 말라붙는다.

    TRUNCATE 가 아닌 DELETE 인 이유는 락이다. TRUNCATE 의 ACCESS EXCLUSIVE 는
    읽는 쪽을 막지만 DELETE 는 MVCC 스냅샷으로 지나가게 둔다.
    """
    await session.execute(text("DELETE FROM overseas_spot_matches"))
    await session.execute(
        text(_REBUILD_SQL), {"candidates": candidates, "distance_max": distance_max}
    )
    row = (
        await session.execute(
            text(
                "SELECT count(*) AS targets, "
                "count(*) FILTER (WHERE m.full3) AS matched "
                "FROM overseas_spots o "
                "LEFT JOIN LATERAL ("
                "SELECT count(*) = 3 AS full3 FROM overseas_spot_matches m "
                "WHERE m.overseas_id = o.id"
                ") m ON true "
                "WHERE o.embedding IS NOT NULL"
            )
        )
    ).one()
    return {
        "targets": int(row.targets),
        "matched": int(row.matched or 0),
        "empty": int(row.targets) - int(row.matched or 0),
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


@dataclass(frozen=True)
class HomeSpotRow:
    content_id: str
    title: str
    first_image_url: str | None
    cpyrht_div_cd: str | None
    category: str | None
    region_name: str | None
    sigungu_name: str | None
    dist: float | None = None
    anchor_content_id: str | None = None
    base_ymd: date | None = None
    lat: float | None = None
    lng: float | None = None


_SPOT_COLUMNS_SQL = """
       spots.content_id,
       spots.title,
       spots.first_image_url,
       spots.cpyrht_div_cd,
       c.lcls_systm3_nm AS category,
       r.ldong_regn_nm AS region_name,
       sg.ldong_signgu_nm AS sigungu_name,
       spots.mapy AS lat,
       spots.mapx AS lng
"""

_SPOT_JOINS_SQL = """
    LEFT JOIN lcls_systm_codes c ON c.lcls_systm3_cd = spots.lcls_systm3
    LEFT JOIN regions r ON r.ldong_regn_cd = spots.ldong_regn_cd
    LEFT JOIN sigungus sg ON sg.ldong_signgu_cd = spots.ldong_signgu_cd
"""

_HAVERSINE_SQL = """
    6371000.0 * acos(least(1.0, greatest(-1.0,
        cos(radians((:lat)::double precision))
      * cos(radians(spots.mapy::double precision))
      * cos(radians(spots.mapx::double precision) - radians((:lng)::double precision))
      + sin(radians((:lat)::double precision))
      * sin(radians(spots.mapy::double precision))
    )))
"""

_NEARBY_SIGNAL_SCORE = (
    "coalesce(sc.concentration_rate, 0) / 100.0"
    " + ln(1 + least(coalesce(bz.base_total, 0), 100000)) / 12.0"
    " + coalesce(v.aesthetic_score, 0)"
)

_NEARBY_BUZZ_LATERAL = """
LEFT JOIN LATERAL (
    SELECT max(b.blog_total) AS base_total
    FROM spot_buzz b
    WHERE b.content_id = spots.content_id AND b.scope = 'base'
) bz ON true
"""


def _nearby_category_sql(category_predicate: str) -> str:
    return f"""
SELECT * FROM (
    SELECT {_SPOT_COLUMNS_SQL},
           sc.concentration_rate AS rate,
           sc.base_ymd AS base_ymd,
           {_NEARBY_SIGNAL_SCORE} AS score,
           {_HAVERSINE_SQL} AS dist
    FROM spots
    LEFT JOIN spot_concentration sc ON sc.content_id = spots.content_id
    LEFT JOIN spot_visual v ON v.content_id = spots.content_id
    {_NEARBY_BUZZ_LATERAL}
    {_SPOT_JOINS_SQL}
    WHERE spots.show_flag = 1
      AND spots.first_image_url IS NOT NULL
      AND spots.first_image_url <> ''
      AND spots.mapx IS NOT NULL
      AND spots.mapy IS NOT NULL
      AND spots.mapy BETWEEN (:min_lat)::double precision AND (:max_lat)::double precision
      AND spots.mapx BETWEEN (:min_lng)::double precision AND (:max_lng)::double precision
      AND ({category_predicate})
) near
WHERE dist <= (:radius)::double precision
ORDER BY score DESC, dist ASC, content_id ASC
LIMIT (:lim)::int
"""


_NEARBY_CATEGORY_SQL: dict[str, str] = {
    "spot": _nearby_category_sql(travel_category_sql()),
    "cafe": _nearby_category_sql(category_sql(NearbyCategory.cafe)),
    "food": _nearby_category_sql(category_sql(NearbyCategory.food)),
}


def _taste_picks_concentration_sql(category_sql: str, *, ascending: bool) -> str:
    direction = "ASC" if ascending else "DESC"
    return f"""
SELECT content_id, title, first_image_url, cpyrht_div_cd, category, region_name, sigungu_name,
       lat, lng
FROM (
    SELECT DISTINCT ON (spots.ldong_signgu_cd)
           {_SPOT_COLUMNS_SQL},
           sc.concentration_rate AS rate
    FROM spots
    JOIN spot_concentration sc ON sc.content_id = spots.content_id
    {_SPOT_JOINS_SQL}
    WHERE spots.show_flag = 1
      AND spots.first_image_url IS NOT NULL
      AND spots.first_image_url <> ''
      AND ({category_sql})
      AND EXISTS (SELECT 1 FROM spot_embeddings e WHERE e.content_id = spots.content_id)
    ORDER BY spots.ldong_signgu_cd, sc.concentration_rate {direction}, spots.content_id
) picks
ORDER BY rate {direction}, content_id
LIMIT (:lim)::int
"""


def _taste_picks_shuffle_sql(category_sql: str) -> str:
    return f"""
SELECT content_id, title, first_image_url, cpyrht_div_cd, category, region_name, sigungu_name,
       lat, lng
FROM (
    SELECT DISTINCT ON (spots.ldong_signgu_cd)
           {_SPOT_COLUMNS_SQL},
           md5(spots.content_id) AS shuffle_key
    FROM spots
    {_SPOT_JOINS_SQL}
    WHERE spots.show_flag = 1
      AND spots.first_image_url IS NOT NULL
      AND spots.first_image_url <> ''
      AND ({category_sql})
      AND EXISTS (SELECT 1 FROM spot_embeddings e WHERE e.content_id = spots.content_id)
    ORDER BY spots.ldong_signgu_cd, md5(spots.content_id)
) picks
ORDER BY shuffle_key
LIMIT (:lim)::int
"""


_FESTA_CATEGORY_SQL = "spots.lcls_systm1 = 'EV'"

_TASTE_PICKS_SQL = _taste_picks_concentration_sql(_CATEGORY_SQL, ascending=False)

_TASTE_CATEGORY_PICKS_SQL: dict[str, str] = {
    "SPOT": _TASTE_PICKS_SQL,
    "HIDDEN": _taste_picks_concentration_sql(_CATEGORY_SQL, ascending=True),
    "CAFE": _taste_picks_shuffle_sql(category_sql(NearbyCategory.cafe)),
    "FOOD": _taste_picks_shuffle_sql(category_sql(NearbyCategory.food)),
    "FESTA": _taste_picks_shuffle_sql(_FESTA_CATEGORY_SQL),
}

_CURATION_SLOT_SQL = f"""
SELECT {_SPOT_COLUMNS_SQL}
FROM spots
{_SPOT_JOINS_SQL}
LEFT JOIN spot_visual v ON v.content_id = spots.content_id
WHERE spots.show_flag = 1
  AND spots.first_image_url IS NOT NULL
  AND spots.first_image_url <> ''
  AND sg.ldong_signgu_nm = :sigungu
  AND ({{category}})
ORDER BY v.aesthetic_score DESC NULLS LAST, spots.content_id
LIMIT (:lim)::int
"""


_TASTE_NEIGHBORS_SQL = f"""
WITH seed AS (
    SELECT se.content_id, se.embedding::vector(512) AS emb
    FROM spot_embeddings se
    WHERE se.content_id = ANY(CAST(:seed_ids AS text[]))
), centroid AS (
    SELECT AVG(emb)::halfvec(512) AS vec FROM seed
), hit AS (
    SELECT spots.content_id,
           spots.title,
           spots.first_image_url,
           spots.cpyrht_div_cd,
           spots.lcls_systm3,
           spots.ldong_regn_cd,
           spots.ldong_signgu_cd,
           se.embedding AS emb,
           (se.embedding <=> (SELECT vec FROM centroid))::float AS score,
           {_HAVERSINE_SQL} AS dist
    FROM spot_embeddings se
    JOIN spots ON spots.content_id = se.content_id
              AND spots.show_flag = 1
              AND spots.first_image_url IS NOT NULL
              AND spots.first_image_url <> ''
              AND ({_CATEGORY_SQL})
    WHERE se.content_id <> ALL (CAST(:seed_ids AS text[]))
      AND (SELECT vec FROM centroid) IS NOT NULL
    ORDER BY se.embedding <=> (SELECT vec FROM centroid)
    LIMIT (:lim)::int
)
SELECT spots.content_id,
       spots.title,
       spots.first_image_url,
       spots.cpyrht_div_cd,
       c.lcls_systm3_nm AS category,
       r.ldong_regn_nm AS region_name,
       sg.ldong_signgu_nm AS sigungu_name,
       spots.dist,
       anchor.content_id AS anchor_content_id
FROM hit AS spots
LEFT JOIN lcls_systm_codes c ON c.lcls_systm3_cd = spots.lcls_systm3
LEFT JOIN regions r ON r.ldong_regn_cd = spots.ldong_regn_cd
LEFT JOIN sigungus sg ON sg.ldong_signgu_cd = spots.ldong_signgu_cd
LEFT JOIN LATERAL (
    SELECT seed.content_id
    FROM seed
    ORDER BY seed.emb::halfvec(512) <=> spots.emb
    LIMIT 1
) anchor ON true
ORDER BY spots.score, spots.content_id
"""


async def fetch_nearby_by_category(
    session: AsyncSession,
    *,
    category: str,
    lat: float,
    lng: float,
    min_lat: float,
    max_lat: float,
    min_lng: float,
    max_lng: float,
    radius: float,
    limit: int,
) -> list[HomeSpotRow]:
    result = await session.execute(
        text(_NEARBY_CATEGORY_SQL[category]),
        {
            "lat": lat,
            "lng": lng,
            "min_lat": min_lat,
            "max_lat": max_lat,
            "min_lng": min_lng,
            "max_lng": max_lng,
            "radius": radius,
            "lim": limit,
        },
    )
    return [_home_spot_row(row) for row in result]


async def fetch_curation_slot(
    session: AsyncSession, *, sigungu: str, category: str, limit: int
) -> list[HomeSpotRow]:
    sql = _CURATION_SLOT_SQL.format(category=category)
    result = await session.execute(text(sql), {"sigungu": sigungu, "lim": limit})
    return [_home_spot_row(row) for row in result]


async def fetch_taste_picks(
    session: AsyncSession, *, limit: int, category: str | None = None
) -> list[HomeSpotRow]:
    sql = _TASTE_CATEGORY_PICKS_SQL.get(category or "", _TASTE_PICKS_SQL)
    result = await session.execute(text(sql), {"lim": limit})
    return [_home_spot_row(row) for row in result]


async def fetch_taste_neighbors(
    session: AsyncSession,
    *,
    seed_ids: list[str],
    lat: float | None,
    lng: float | None,
    limit: int,
) -> list[HomeSpotRow]:
    if not seed_ids:
        return []
    result = await session.execute(
        text(_TASTE_NEIGHBORS_SQL),
        {"seed_ids": seed_ids, "lat": lat, "lng": lng, "lim": limit},
    )
    return [_home_spot_row(row) for row in result]


def _home_spot_row(row: Any) -> HomeSpotRow:
    mapping = row._mapping
    dist = mapping.get("dist")
    return HomeSpotRow(
        content_id=mapping["content_id"],
        title=mapping["title"] or "",
        first_image_url=mapping["first_image_url"],
        cpyrht_div_cd=mapping["cpyrht_div_cd"],
        category=mapping["category"],
        region_name=mapping["region_name"],
        sigungu_name=mapping["sigungu_name"],
        dist=float(dist) if dist is not None else None,
        anchor_content_id=mapping.get("anchor_content_id"),
        base_ymd=mapping.get("base_ymd"),
        lat=_coord(mapping.get("lat")),
        lng=_coord(mapping.get("lng")),
    )


def _coord(value: Any) -> float | None:
    return float(value) if value is not None else None
