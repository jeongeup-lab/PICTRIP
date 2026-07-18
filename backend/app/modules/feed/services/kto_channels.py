from __future__ import annotations

import asyncio
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
_FESTA_MAX_PAGES = 5
_FESTA_PAGE_ROWS = 100
_PETS_TAG = "반려동물 동반 가능"
_PETS_CONTENT_TYPE_ATTRACTION = 12

_CACHE_VERSION = "v4"
_STALE_TTL = 3 * 24 * 3600

_refreshing: set[str] = set()
_bg_tasks: set[asyncio.Task[Any]] = set()


def _today() -> date:
    return datetime.now(KST).date()


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
    items: list[dict[str, Any]] = []
    for page in range(1, _FESTA_MAX_PAGES + 1):
        page_items = await kto.call(
            KtoService.KOR,
            "searchFestival2",
            eventStartDate=window_start,
            numOfRows=_FESTA_PAGE_ROWS,
            pageNo=page,
            arrange="C",
        )
        items.extend(page_items)
        if len(page_items) < _FESTA_PAGE_ROWS:
            break
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
                cpyrht_div_cd=str(it.get("cpyrhtDivCd") or "") or None,
            )
        )
    cards.sort(key=lambda c: int((c.dday or "D-999")[2:]))
    return cards[:_CARD_COUNT]


async def fetch_pets_cards(kto: KtoClient, *, today: date | None = None) -> list[ChannelCardRow]:
    items = await kto.call(
        KtoService.PET,
        "areaBasedList2",
        numOfRows=_ROWS,
        arrange="C",
        contentTypeId=_PETS_CONTENT_TYPE_ATTRACTION,
    )
    pool = [
        ChannelCardRow(
            content_id=str(it["contentid"]),
            title=it["title"],
            region_label=_short_addr(it.get("addr1")),
            image_url=img,
            tag=_PETS_TAG,
            saveable=True,
            cpyrht_div_cd=str(it.get("cpyrhtDivCd") or "") or None,
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
            region_label="",
            image_url=img,
            line=str(it.get("galPhotographyLocation") or "") or None,
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


def _cache_key(key: str) -> str:
    return f"channel:{key}:{_CACHE_VERSION}"


def _encode(cards: list[ChannelCardRow]) -> str:
    return json.dumps(
        {"date": _today().isoformat(), "cards": [asdict(c) for c in cards]},
        ensure_ascii=False,
    )


async def _fetch_and_store(redis: Redis, kto: KtoClient, key: str) -> list[ChannelCardRow]:
    cards = await _FETCHERS[key](kto)
    try:
        await redis.set(_cache_key(key), _encode(cards), ex=_STALE_TTL)
    except Exception as exc:
        logger.warning("feed.channel.cache_set_failed", key=key, error=str(exc))
    return cards


def _spawn_refresh(redis: Redis, kto: KtoClient, key: str) -> None:
    if key in _refreshing:
        return
    _refreshing.add(key)

    async def _run() -> None:
        try:
            await _fetch_and_store(redis, kto, key)
        except Exception as exc:
            logger.warning("feed.channel.refresh_failed", key=key, error=str(exc))
        finally:
            _refreshing.discard(key)

    task = asyncio.create_task(_run())
    _bg_tasks.add(task)
    task.add_done_callback(_bg_tasks.discard)


async def warm_all_channels(redis: Redis, kto: KtoClient) -> dict[str, bool]:
    async def _one(key: str) -> bool:
        try:
            await _fetch_and_store(redis, kto, key)
        except Exception as exc:
            logger.warning("feed.channel.warm_failed", key=key, error=str(exc))
            return False
        return True

    keys = list(_FETCHERS)
    outcomes = await asyncio.gather(*(_one(key) for key in keys))
    return dict(zip(keys, outcomes, strict=True))


async def load_kto_channel_cached(redis: Redis, kto: KtoClient, key: str) -> list[ChannelCardRow]:
    try:
        raw = await redis.get(_cache_key(key))
    except Exception as exc:
        logger.warning("feed.channel.cache_get_failed", key=key, error=str(exc))
        raw = None
    if raw:
        try:
            doc = json.loads(raw)
            cards = [ChannelCardRow(**d) for d in doc["cards"]]
        except (ValueError, TypeError, KeyError) as exc:
            logger.warning("feed.channel.cache_corrupt", key=key, error=str(exc))
        else:
            if doc.get("date") != _today().isoformat():
                _spawn_refresh(redis, kto, key)
            return cards
    return await _fetch_and_store(redis, kto, key)
