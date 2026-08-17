from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from dataclasses import dataclass, replace
from typing import Any, TypeVar

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.kto.client import KtoClient
from app.kto.display import T1_TILE_WIDTH, t1_display_url
from app.web.errors import ResourceNotFound

CHANNEL_LABELS = {
    "spot": "SPOT",
    "cafe": "CAFE",
    "food": "FOOD",
    "festa": "FESTA",
    "hidden": "HIDDEN",
}

SIGNAL_KEYS = ("spot", "cafe", "food", "hidden")
_META_TIMEOUT = 4.0
_T = TypeVar("_T")


@dataclass(frozen=True)
class ChannelMetaRow:
    key: str
    label: str
    thumbnail_url: str | None
    available: bool


@dataclass(frozen=True)
class ChannelCardRow:
    content_id: str | None
    title: str
    region_label: str
    image_url: str | None
    dist: float | None = None
    rank: int | None = None
    dday: str | None = None
    line: str | None = None
    tag: str | None = None
    saveable: bool = True
    cpyrht_div_cd: str | None = None


async def load_channel_cards(
    session: AsyncSession,
    redis: Redis,
    kto: KtoClient,
    *,
    key: str,
    lat: float | None,
    lng: float | None,
) -> list[ChannelCardRow]:
    if key not in CHANNEL_LABELS:
        raise ResourceNotFound(f"unknown channel {key}")
    if key in SIGNAL_KEYS:
        from app.modules.feed.services.signal_channels import load_signal_channel_cached

        return await load_signal_channel_cached(session, redis, key)
    cards = await _load_kto_channel(redis, kto, key)
    return await _drop_unresolvable_details(session, cards)


async def _load_kto_channel(redis: Redis, kto: KtoClient, key: str) -> list[ChannelCardRow]:
    from app.modules.feed.services.kto_channels import load_kto_channel_cached

    return await load_kto_channel_cached(redis, kto, key)


async def _drop_unresolvable_details(
    session: AsyncSession, cards: list[ChannelCardRow]
) -> list[ChannelCardRow]:
    content_ids = [c.content_id for c in cards if c.content_id]
    if not content_ids:
        return cards
    result = await session.execute(
        text(
            "SELECT content_id FROM spots "
            "WHERE content_id = ANY(CAST(:ids AS text[])) AND show_flag = 1"
        ),
        {"ids": content_ids},
    )
    visible = {row.content_id for row in result}
    return [
        c
        if c.content_id is None or c.content_id in visible
        else replace(c, content_id=None, saveable=False)
        for c in cards
    ]


async def _safe(coro: Coroutine[Any, Any, _T]) -> _T | None:
    try:
        return await coro
    except Exception:
        return None


def _first_image(rows: list[Any]) -> str | None:
    for r in rows:
        img: str | None = getattr(r, "image_url", None) or getattr(r, "first_image_url", None)
        if img:
            return t1_display_url(img, getattr(r, "cpyrht_div_cd", None), width=T1_TILE_WIDTH)
    return None


def _meta_from_rows(key: str, rows: list[Any]) -> ChannelMetaRow:
    return ChannelMetaRow(key, CHANNEL_LABELS[key], _first_image(rows), True)


def _meta_or_unavailable(key: str, rows: list[Any] | None) -> ChannelMetaRow:
    if rows is None:
        return ChannelMetaRow(key, CHANNEL_LABELS[key], None, False)
    return _meta_from_rows(key, rows)


async def load_channel_metas(
    session: AsyncSession, redis: Redis, kto: KtoClient
) -> list[ChannelMetaRow]:
    from app.modules.feed.services.kto_channels import load_kto_channel_cached
    from app.modules.feed.services.signal_channels import load_signal_channel_cached

    festa_task = asyncio.ensure_future(
        _safe(asyncio.wait_for(load_kto_channel_cached(redis, kto, "festa"), _META_TIMEOUT))
    )
    spot = await load_signal_channel_cached(session, redis, "spot")
    cafe = await load_signal_channel_cached(session, redis, "cafe")
    food = await load_signal_channel_cached(session, redis, "food")
    hidden = await load_signal_channel_cached(session, redis, "hidden")
    festa = await festa_task
    metas = [
        _meta_or_unavailable("spot", spot or None),
        _meta_or_unavailable("cafe", cafe or None),
        _meta_or_unavailable("food", food or None),
    ]
    if festa is None:
        metas.append(ChannelMetaRow("festa", CHANNEL_LABELS["festa"], None, False))
    elif festa:
        metas.append(_meta_from_rows("festa", festa))
    metas.append(_meta_or_unavailable("hidden", hidden or None))
    return metas
