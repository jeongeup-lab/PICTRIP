from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.modules.feed.services.channels import ChannelCardRow
from app.modules.spots.categories import NearbyCategory, category_sql, travel_category_sql

logger = get_logger(__name__)

CARD_COUNT = 10
_CACHE_VERSION = "v1"
_TTL = 3600

_BUZZ_LATERAL = """
LEFT JOIN LATERAL (
    SELECT
        max(b.mentions) FILTER (WHERE b.scope LIKE :theme_like) AS grid_mentions,
        max(b.recent_ratio) AS recent_ratio,
        max(b.blog_total) FILTER (WHERE b.scope = 'base') AS base_total
    FROM spot_buzz b
    WHERE b.content_id = spots.content_id
) bz ON true
"""

_REGION_RESOLVE_SQL = """
SELECT spots.ldong_regn_cd
FROM spots
WHERE spots.show_flag = 1
  AND spots.mapx IS NOT NULL
  AND spots.mapy IS NOT NULL
  AND spots.ldong_regn_cd IS NOT NULL
  AND spots.mapy BETWEEN (:lat)::double precision - 0.5 AND (:lat)::double precision + 0.5
  AND spots.mapx BETWEEN (:lng)::double precision - 0.6 AND (:lng)::double precision + 0.6
ORDER BY (spots.mapy - (:lat)::double precision) ^ 2
       + (spots.mapx - (:lng)::double precision) ^ 2
LIMIT 1
"""

_SELECT = """
SELECT content_id, title, region_label, first_image_url, cpyrht_div_cd, tag
FROM (
    SELECT DISTINCT ON ({dedup_col})
           spots.content_id,
           spots.title,
           coalesce(r.ldong_regn_nm, '') || ' ' || coalesce(g.ldong_signgu_nm, '') AS region_label,
           spots.first_image_url,
           spots.cpyrht_div_cd,
           {tag_expr} AS tag,
           {score_expr} AS score
    FROM spots
    JOIN spot_visual v ON v.content_id = spots.content_id
    {buzz_lateral}
    LEFT JOIN spot_concentration sc ON sc.content_id = spots.content_id
    LEFT JOIN regions r ON r.ldong_regn_cd = spots.ldong_regn_cd
    LEFT JOIN sigungus g ON g.ldong_signgu_cd = spots.ldong_signgu_cd
    WHERE spots.show_flag = 1
      AND spots.first_image_url IS NOT NULL
      AND spots.first_image_url <> ''
      AND ({fence})
      AND ({cut})
    ORDER BY {dedup_col}, {score_expr} DESC, spots.content_id
) picks
ORDER BY score DESC, content_id
LIMIT :lim
"""

_BUZZ_SCORE = (
    "ln(1 + least(coalesce(bz.base_total, 0), 100000)) + coalesce(bz.grid_mentions, 0) * 0.5"
)


def _channel_sql(key: str, *, scoped: bool = False) -> str:
    if key == "spot":
        return _render(
            key,
            scoped,
            tag_expr="'요즘뜨는'",
            score_expr=f"coalesce(bz.recent_ratio, 0) * 6 + v.aesthetic_score * 10 + {_BUZZ_SCORE}",
            buzz_lateral=_BUZZ_LATERAL,
            fence=travel_category_sql(),
            cut=(
                "v.aesthetic_score > 0 AND coalesce(bz.recent_ratio, 0) >= 0.5 "
                "AND (bz.grid_mentions IS NOT NULL OR coalesce(bz.base_total, 0) >= 500)"
            ),
        )
    if key == "cafe":
        return _render(
            key,
            scoped,
            tag_expr="CASE WHEN v.photo_type = 'view' THEN '뷰맛집' ELSE '감성' END",
            score_expr=f"v.aesthetic_score * 20 + {_BUZZ_SCORE}",
            buzz_lateral=_BUZZ_LATERAL,
            fence=category_sql(NearbyCategory.cafe),
            cut=(
                "v.aesthetic_score > 0.02 "
                "AND (bz.grid_mentions IS NOT NULL OR coalesce(bz.base_total, 0) >= 200)"
            ),
        )
    if key == "food":
        return _render(
            key,
            scoped,
            tag_expr="CASE WHEN v.photo_type = 'food' THEN '비주얼' ELSE '맛집' END",
            score_expr=(
                f"{_BUZZ_SCORE} "
                "+ CASE WHEN v.photo_type = 'food' THEN greatest(v.aesthetic_score, 0) * 10 "
                "ELSE 0 END"
            ),
            buzz_lateral=_BUZZ_LATERAL,
            fence=category_sql(NearbyCategory.food),
            cut="bz.grid_mentions IS NOT NULL OR coalesce(bz.base_total, 0) >= 1000",
        )
    if key == "hidden":
        return _render(
            key,
            False,
            tag_expr="'숨은명소'",
            score_expr="coalesce(bz.recent_ratio, 0) * 4 + v.aesthetic_score * 10",
            buzz_lateral=_BUZZ_LATERAL,
            fence=travel_category_sql(),
            cut=(
                "v.aesthetic_score > 0 AND coalesce(bz.recent_ratio, 0) >= 0.6 "
                "AND coalesce(bz.base_total, 100000) <= 30000 "
                "AND (sc.content_id IS NULL OR sc.concentration_rate < 30)"
            ),
        )
    raise ValueError(f"unknown signal channel {key}")


def _render(_key: str, scoped: bool, **kwargs: str) -> str:
    fence = kwargs.pop("fence")
    if scoped:
        fence = f"({fence}) AND spots.ldong_regn_cd = :region_cd"
        dedup = "spots.ldong_signgu_cd"
    else:
        dedup = "spots.ldong_regn_cd"
    return _SELECT.format(dedup_col=dedup, fence=fence, **kwargs)


def _cache_key(key: str, region_cd: str | None) -> str:
    return f"channel:sig:{key}:{region_cd or 'all'}:{_CACHE_VERSION}"


async def resolve_region_cd(
    session: AsyncSession, lat: float | None, lng: float | None
) -> str | None:
    if lat is None or lng is None:
        return None
    row = (await session.execute(text(_REGION_RESOLVE_SQL), {"lat": lat, "lng": lng})).first()
    return row.ldong_regn_cd if row else None


async def _query(
    session: AsyncSession, key: str, *, region_cd: str | None = None
) -> list[ChannelCardRow]:
    theme = key if key in ("cafe", "food") else "spot"
    rows: list[Any] = []
    if region_cd is not None and key != "hidden":
        params: dict[str, Any] = {
            "lim": CARD_COUNT,
            "theme_like": f"%:{theme}",
            "region_cd": region_cd,
        }
        result = await session.execute(text(_channel_sql(key, scoped=True)), params)
        rows = list(result)
    if len(rows) < CARD_COUNT:
        result = await session.execute(
            text(_channel_sql(key)),
            {"lim": CARD_COUNT, "theme_like": f"%:{theme}"},
        )
        seen = {row.content_id for row in rows}
        rows.extend(row for row in result if row.content_id not in seen)
        rows = rows[:CARD_COUNT]
    return [
        ChannelCardRow(
            content_id=row.content_id,
            title=row.title,
            region_label=row.region_label.strip(),
            image_url=row.first_image_url,
            rank=i + 1,
            tag=row.tag,
            cpyrht_div_cd=row.cpyrht_div_cd,
        )
        for i, row in enumerate(rows)
    ]


async def load_signal_channel_cached(
    session: AsyncSession, redis: Redis, key: str, *, region_cd: str | None = None
) -> list[ChannelCardRow]:
    if key == "hidden":
        region_cd = None
    ck = _cache_key(key, region_cd)
    try:
        raw = await redis.get(ck)
    except Exception as exc:
        logger.warning("feed.channel.cache_get_failed", key=key, error=str(exc))
        raw = None
    if raw:
        try:
            return [ChannelCardRow(**d) for d in json.loads(raw)]
        except (ValueError, TypeError, KeyError) as exc:
            logger.warning("feed.channel.cache_corrupt", key=key, error=str(exc))
    cards = await _query(session, key, region_cd=region_cd)
    if cards:
        try:
            await redis.set(ck, json.dumps([asdict(c) for c in cards], ensure_ascii=False), ex=_TTL)
        except Exception as exc:
            logger.warning("feed.channel.cache_set_failed", key=key, error=str(exc))
    return cards
