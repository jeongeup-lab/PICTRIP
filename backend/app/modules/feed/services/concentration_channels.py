from __future__ import annotations

import json
from dataclasses import asdict

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.modules.feed.services.channels import ChannelCardRow
from app.modules.spots import services as spots_services

logger = get_logger(__name__)

_CARD_COUNT = 10
_CACHE_VERSION = "v4"
_TTL = 3600


def _cache_key(key: str) -> str:
    return f"channel:{key}:{_CACHE_VERSION}"


async def _query(session: AsyncSession, key: str) -> list[ChannelCardRow]:
    load = spots_services.load_hot_spots if key == "hot" else spots_services.load_hidden_spots
    rows = await load(session, limit=_CARD_COUNT)
    return [
        ChannelCardRow(
            content_id=r.content_id,
            title=r.title,
            region_label=r.region_label,
            image_url=r.first_image_url,
            rank=r.rank,
            cpyrht_div_cd=r.cpyrht_div_cd,
        )
        for r in rows
    ]


async def load_concentration_channel_cached(
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
