from __future__ import annotations

import json
from dataclasses import asdict

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.modules.feed.services.channels import ChannelCardRow
from app.modules.spots.services import (
    NearbyCategory,
    category_sql,
    travel_category_sql,
)

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

_SELECT = """
SELECT content_id, title, region_label, first_image_url, cpyrht_div_cd, tag
FROM (
    SELECT DISTINCT ON (spots.ldong_regn_cd)
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
    ORDER BY spots.ldong_regn_cd, {score_expr} DESC, spots.content_id
) picks
ORDER BY score DESC, content_id
LIMIT :lim
"""

_BUZZ_SCORE = (
    "ln(1 + least(coalesce(bz.base_total, 0), 100000)) + coalesce(bz.grid_mentions, 0) * 0.5"
)


def _channel_sql(key: str) -> str:
    if key == "spot":
        return _SELECT.format(
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
        return _SELECT.format(
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
        return _SELECT.format(
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
        return _SELECT.format(
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


def _cache_key(key: str) -> str:
    return f"channel:sig:{key}:{_CACHE_VERSION}"


async def _query(session: AsyncSession, key: str) -> list[ChannelCardRow]:
    theme = key if key in ("cafe", "food") else "spot"
    result = await session.execute(
        text(_channel_sql(key)),
        {"lim": CARD_COUNT, "theme_like": f"%:{theme}"},
    )
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
        for i, row in enumerate(result)
    ]


async def load_signal_channel_cached(
    session: AsyncSession, redis: Redis, key: str
) -> list[ChannelCardRow]:
    ck = _cache_key(key)
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
    cards = await _query(session, key)
    if cards:
        try:
            await redis.set(ck, json.dumps([asdict(c) for c in cards], ensure_ascii=False), ex=_TTL)
        except Exception as exc:
            logger.warning("feed.channel.cache_set_failed", key=key, error=str(exc))
    return cards
