"""REC service layer.

`get_today_inspo` returns a daily-stable inspo spot: deterministic per KST day,
Redis-cached for the rest of the day. Date/seed + caching live here; the spot
query lives in spots.services (cross-module reads go through services, not models).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ResourceNotFound
from app.core.logging import get_logger
from app.core.redis import redis_cache
from app.modules.spots.services import SpotCardRow, pick_active_spot_by_seed

logger = get_logger(__name__)

_KST = ZoneInfo("Asia/Seoul")
_CACHE_KEY = "rec:today_inspo:{date}"


def _kst_now() -> datetime:
    return datetime.now(_KST)


def _seed_for_date(date_iso: str) -> int:
    """Stable integer seed from an ISO date. Hashing avoids adjacent days
    landing on adjacent offsets."""
    return int(hashlib.sha256(date_iso.encode()).hexdigest(), 16)


def _seconds_until_kst_midnight(now: datetime) -> int:
    """TTL so the cached card expires exactly at the next KST midnight."""
    tomorrow = (now + timedelta(days=1)).date()
    midnight = datetime.combine(tomorrow, datetime.min.time(), tzinfo=_KST)
    return max(1, int((midnight - now).total_seconds()))


def _card_to_dict(card: SpotCardRow) -> dict[str, Any]:
    return {
        "contentId": card.content_id,
        "title": card.title,
        "firstImageUrl": card.first_image_url,
        "addr1": card.addr1,
        "mapx": card.mapx,
        "mapy": card.mapy,
    }


def _dict_to_card(data: dict[str, Any]) -> SpotCardRow:
    return SpotCardRow(
        content_id=data["contentId"],
        title=data["title"],
        first_image_url=data["firstImageUrl"],
        addr1=data["addr1"],
        mapx=data["mapx"],
        mapy=data["mapy"],
    )


async def _cache_get(key: str) -> dict[str, Any] | None:
    try:
        raw = await redis_cache.get(key)
    except RedisError:
        logger.warning("today_inspo_cache_get_failed", key=key)
        return None
    if raw is None:
        return None
    try:
        decoded: dict[str, Any] = json.loads(raw)
    except (ValueError, TypeError):
        logger.warning("today_inspo_cache_decode_failed", key=key)
        return None
    return decoded


async def _cache_set(key: str, value: dict[str, Any], ttl: int) -> None:
    try:
        await redis_cache.set(key, json.dumps(value), ex=ttl)
    except RedisError:
        logger.warning("today_inspo_cache_set_failed", key=key)


async def get_today_inspo(session: AsyncSession) -> SpotCardRow:
    """Daily-stable inspo spot, deterministic per KST day and Redis-cached.

    Redis is an optimization, not the source of truth: a cold or failed cache
    recomputes the same spot from the date seed. Raises ResourceNotFound if
    there is no eligible spot.
    """
    now = _kst_now()
    date_iso = now.date().isoformat()
    cache_key = _CACHE_KEY.format(date=date_iso)

    cached = await _cache_get(cache_key)
    if cached is not None:
        return _dict_to_card(cached)

    card = await pick_active_spot_by_seed(session, _seed_for_date(date_iso))
    if card is None:
        raise ResourceNotFound("추천할 영감 spot이 없습니다.")

    await _cache_set(cache_key, _card_to_dict(card), _seconds_until_kst_midnight(now))
    return card
