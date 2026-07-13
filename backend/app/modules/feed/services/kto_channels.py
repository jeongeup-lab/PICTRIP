"""festa·pets·snap 채널 — 라이브 KTO fetch + KST 자정까지 Redis 캐시."""

from __future__ import annotations

import json
import random
from collections.abc import Awaitable, Callable
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
from typing import Any

from redis.asyncio import Redis

from app.core.kto_client import KtoClient, KtoService
from app.core.logging import get_logger
from app.modules.feed.services.channels import ChannelCardRow

logger = get_logger(__name__)

KST = timezone(timedelta(hours=9))
_ROWS = 30
_CARD_COUNT = 10
_FESTA_WINDOW_DAYS = 90
_PETS_TAG = "반려동물 동반 가능"


def _today() -> date:
    return datetime.now(KST).date()


def _ttl_until_kst_midnight() -> int:
    now = datetime.now(KST)
    midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(int((midnight - now).total_seconds()), 60)


def _parse_ymd(raw: Any) -> date | None:
    if not raw:
        return None
    try:
        return datetime.strptime(str(raw), "%Y%m%d").date()
    except ValueError:
        return None


def _short_addr(addr: Any) -> str:
    if not addr:
        return ""
    return " ".join(str(addr).split()[:2])


def _https(url: Any) -> str | None:
    if not url:
        return None
    text = str(url)
    if text.startswith("http://"):
        return "https://" + text[len("http://") :]
    return text


async def fetch_festa_cards(kto: KtoClient, *, today: date | None = None) -> list[ChannelCardRow]:
    today = today or _today()
    window_start = (today - timedelta(days=_FESTA_WINDOW_DAYS)).strftime("%Y%m%d")
    items = await kto.call(
        KtoService.KOR,
        "searchFestival2",
        eventStartDate=window_start,
        numOfRows=_ROWS,
        arrange="C",
    )
    cards: list[ChannelCardRow] = []
    for it in items:
        start = _parse_ymd(it.get("eventstartdate"))
        end = _parse_ymd(it.get("eventenddate"))
        img = it.get("firstimage") or None
        if not img or start is None or end is None or start > today or end < today:
            continue
        days = max((end - today).days, 0)
        line = f"{end.month}월 {end.day}일까지"
        addr = _short_addr(it.get("addr1"))
        if addr:
            line = f"{line} · {addr}"
        cards.append(
            ChannelCardRow(
                content_id=str(it["contentid"]),
                title=it["title"],
                region_label=addr,
                image_url=img,
                dday=f"D-{days}",
                line=line,
                saveable=True,
            )
        )
    cards.sort(key=lambda c: int((c.dday or "D-999")[2:]))
    return cards[:_CARD_COUNT]


async def fetch_pets_cards(kto: KtoClient, *, today: date | None = None) -> list[ChannelCardRow]:
    items = await kto.call(KtoService.PET, "areaBasedList2", numOfRows=_ROWS, arrange="C")
    pool = [
        ChannelCardRow(
            content_id=str(it["contentid"]),
            title=it["title"],
            region_label=_short_addr(it.get("addr1")),
            image_url=img,
            tag=_PETS_TAG,
            saveable=True,
        )
        for it in items
        if (img := it.get("firstimage") or None)
    ]
    if len(pool) <= _CARD_COUNT:
        return pool
    return random.sample(pool, _CARD_COUNT)


async def fetch_snap_cards(kto: KtoClient, *, today: date | None = None) -> list[ChannelCardRow]:
    items = await kto.call(KtoService.GALLERY, "galleryList1", numOfRows=_ROWS, arrange="A")
    cards = [
        ChannelCardRow(
            content_id=None,
            title=it["galTitle"],
            region_label=str(it.get("galPhotographyLocation") or ""),
            image_url=img,
            saveable=False,
        )
        for it in items
        if (img := _https(it.get("galWebImageUrl")))
    ]
    return cards[:_CARD_COUNT]


_FETCHERS: dict[str, Callable[[KtoClient], Awaitable[list[ChannelCardRow]]]] = {
    "festa": fetch_festa_cards,
    "pets": fetch_pets_cards,
    "snap": fetch_snap_cards,
}


async def load_kto_channel_cached(redis: Redis, kto: KtoClient, key: str) -> list[ChannelCardRow]:
    cache_key = f"channel:{key}:v1"
    try:
        raw = await redis.get(cache_key)
        if raw:
            return [ChannelCardRow(**d) for d in json.loads(raw)]
    except Exception as exc:
        logger.warning("feed.channel.cache_get_failed", key=key, error=str(exc))

    cards = await _FETCHERS[key](kto)

    try:
        payload = json.dumps([asdict(c) for c in cards], ensure_ascii=False)
        await redis.set(cache_key, payload, ex=_ttl_until_kst_midnight())
    except Exception as exc:
        logger.warning("feed.channel.cache_set_failed", key=key, error=str(exc))
    return cards
