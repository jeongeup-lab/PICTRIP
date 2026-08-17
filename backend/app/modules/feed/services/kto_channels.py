from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import asdict, replace
from datetime import date, datetime, timedelta, timezone
from typing import Any

from redis.asyncio import Redis

from app.core.logging import get_logger
from app.kto.client import KtoClient, KtoService
from app.modules.feed.services.channels import ChannelCardRow
from app.web.errors import AppError

logger = get_logger(__name__)

KST = timezone(timedelta(hours=9))
_ROWS = 30
_CARD_COUNT = 10
_FESTA_WINDOW_DAYS = 90
_FESTA_MAX_PAGES = 5
_FESTA_PAGE_ROWS = 100
_POOL_WINDOW_DAYS = 365
_POOL_MAX_PAGES = 20
_POOL_PAGE_ROWS = 300
_POOL_WAVE = 4

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


async def _fetch_festival_items(
    kto: KtoClient,
    *,
    window_start: str,
    page_rows: int,
    max_pages: int,
    wave: int,
) -> list[dict[str, Any]]:
    async def _page(page: int) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = await kto.call(
            KtoService.KOR,
            "searchFestival2",
            eventStartDate=window_start,
            numOfRows=page_rows,
            pageNo=page,
            arrange="C",
        )
        return result

    items: list[dict[str, Any]] = []
    for first in range(1, max_pages + 1, wave):
        pages = range(first, min(first + wave, max_pages + 1))
        results = await asyncio.gather(*(_page(page) for page in pages))
        exhausted = False
        for page_items in results:
            items.extend(page_items)
            exhausted = exhausted or len(page_items) < page_rows
        if exhausted:
            break
    return items


def _festival_cards(items: list[dict[str, Any]], *, today: date) -> list[ChannelCardRow]:
    cards: list[ChannelCardRow] = []
    seen: set[str] = set()
    for it in items:
        start = _parse_ymd(it.get("eventstartdate"))
        end = _parse_ymd(it.get("eventenddate"))
        img = it.get("firstimage") or None
        content_id = str(it.get("contentid") or "")
        if (
            not img
            or not content_id
            or start is None
            or end is None
            or start > today
            or end < today
        ):
            continue
        if content_id in seen:
            continue
        seen.add(content_id)
        days = max((end - today).days, 0)
        line = f"{end.month}월 {end.day}일까지"
        addr = _short_addr(it.get("addr1"))
        if addr:
            line = f"{line} · {addr}"
        cards.append(
            ChannelCardRow(
                content_id=content_id,
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
    return cards


async def fetch_festa_cards(kto: KtoClient, *, today: date | None = None) -> list[ChannelCardRow]:
    today = today or _today()
    items = await _fetch_festival_items(
        kto,
        window_start=(today - timedelta(days=_FESTA_WINDOW_DAYS)).strftime("%Y%m%d"),
        page_rows=_FESTA_PAGE_ROWS,
        max_pages=_FESTA_MAX_PAGES,
        wave=1,
    )
    return _festival_cards(items, today=today)[:_CARD_COUNT]


async def fetch_festival_pool_cards(
    kto: KtoClient, *, today: date | None = None
) -> list[ChannelCardRow]:
    today = today or _today()
    items = await _fetch_festival_items(
        kto,
        window_start=(today - timedelta(days=_POOL_WINDOW_DAYS)).strftime("%Y%m%d"),
        page_rows=_POOL_PAGE_ROWS,
        max_pages=_POOL_MAX_PAGES,
        wave=_POOL_WAVE,
    )
    if len(items) >= _POOL_MAX_PAGES * _POOL_PAGE_ROWS:
        logger.warning("feed.festival.pool_page_cap_reached", pages=_POOL_MAX_PAGES)
    return _festival_cards(items, today=today)


_FETCHERS: dict[str, Callable[[KtoClient], Awaitable[list[ChannelCardRow]]]] = {
    "festa": fetch_festa_cards,
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


_FESTIVAL_POOL_KEY = "festival:pool:v2"
_FESTIVAL_POOL_TTL = 2 * 86_400


def _cached_end_date(row: ChannelCardRow, *, cached_on: date) -> date | None:
    if not row.dday or not row.dday.startswith("D-"):
        return None
    try:
        return cached_on + timedelta(days=int(row.dday[2:]))
    except ValueError:
        return None


def _revalidated(
    rows: list[ChannelCardRow], *, cached_on: str | None, today: date
) -> list[ChannelCardRow]:
    try:
        cached_date = date.fromisoformat(cached_on or "")
    except ValueError:
        return []
    shifted: list[ChannelCardRow] = []
    for row in rows:
        end = _cached_end_date(row, cached_on=cached_date)
        if end is None or end < today:
            continue
        line = f"{end.month}월 {end.day}일까지"
        if row.region_label:
            line = f"{line} · {row.region_label}"
        shifted.append(replace(row, dday=f"D-{max((end - today).days, 0)}", line=line))
    shifted.sort(key=lambda c: int((c.dday or "D-999")[2:]))
    return shifted


async def load_festival_pool(
    redis: Redis, kto: KtoClient, *, fetch_timeout: float | None = None
) -> list[ChannelCardRow]:
    try:
        cached = await redis.get(_FESTIVAL_POOL_KEY)
    except Exception as exc:
        logger.warning("feed.festival.cache_get_failed", error=str(exc))
        cached = None
    stale: list[ChannelCardRow] = []
    if cached:
        try:
            payload = json.loads(cached)
            rows = [ChannelCardRow(**row) for row in payload["cards"]]
        except (ValueError, TypeError, KeyError) as exc:
            logger.warning("feed.festival.cache_corrupt", error=str(exc))
        else:
            if payload.get("date") == _today().isoformat():
                return rows
            stale = _revalidated(rows, cached_on=payload.get("date"), today=_today())
    try:
        if fetch_timeout is None:
            cards = await fetch_festival_pool_cards(kto)
        else:
            async with asyncio.timeout(fetch_timeout):
                cards = await fetch_festival_pool_cards(kto)
    except (AppError, TimeoutError):
        if not stale:
            raise
        logger.warning("feed.festival.serving_stale", cards=len(stale))
        return stale
    try:
        await redis.set(
            _FESTIVAL_POOL_KEY,
            json.dumps(
                {"date": _today().isoformat(), "cards": [asdict(c) for c in cards]},
                ensure_ascii=False,
            ),
            ex=_FESTIVAL_POOL_TTL,
        )
    except Exception as exc:
        logger.warning("feed.festival.cache_set_failed", error=str(exc))
    return cards
