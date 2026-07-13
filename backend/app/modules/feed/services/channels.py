from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from dataclasses import dataclass
from typing import Any

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ResourceNotFound, ValidationFailed
from app.core.kto_client import KtoClient
from app.modules.map import services as map_services
from app.modules.map.schemas import NearbySpotCard
from app.modules.spots import services as spots_services

CHANNEL_LABELS = {
    "around": "Around",
    "hot": "Hot",
    "hidden": "Hidden",
    "festa": "Festa",
    "pets": "Pets",
    "snap": "Snap",
}
_CARD_COUNT = 10
_AROUND_RADIUS_M = 5000


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
    if key == "around":
        if lat is None or lng is None:
            raise ValidationFailed("around channel requires lat/lng")
        cards = await map_services.nearby_cards(
            session,
            lat=lat,
            lng=lng,
            radius=_AROUND_RADIUS_M,
            category=None,
            sw_lat=None,
            sw_lng=None,
            ne_lat=None,
            ne_lng=None,
        )
        return [
            ChannelCardRow(
                content_id=c.contentId,
                title=c.title,
                region_label=_region(c),
                image_url=c.firstImageUrl,
                dist=c.dist,
            )
            for c in cards[:_CARD_COUNT]
        ]
    if key == "hot":
        hot_rows = await spots_services.load_hot_spots(session, limit=_CARD_COUNT)
        return [
            ChannelCardRow(
                content_id=r.content_id,
                title=r.title,
                region_label=r.region_label,
                image_url=r.first_image_url,
                rank=r.rank,
            )
            for r in hot_rows
        ]
    if key == "hidden":
        hidden_rows = await spots_services.load_hidden_spots(session, limit=_CARD_COUNT)
        return [
            ChannelCardRow(
                content_id=r.content_id,
                title=r.title,
                region_label=r.region_label,
                image_url=r.first_image_url,
            )
            for r in hidden_rows
        ]
    return await _load_kto_channel(redis, kto, key)


async def _load_kto_channel(redis: Redis, kto: KtoClient, key: str) -> list[ChannelCardRow]:
    from app.modules.feed.services.kto_channels import load_kto_channel_cached

    return await load_kto_channel_cached(redis, kto, key)


async def _safe[T](coro: Coroutine[Any, Any, T]) -> T | None:
    try:
        return await coro
    except Exception:
        return None


def _first_image(rows: list[Any]) -> str | None:
    for r in rows:
        img: str | None = getattr(r, "image_url", None) or getattr(r, "first_image_url", None)
        if img:
            return img
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

    hot, hidden, festa, pets, snap = await asyncio.gather(
        spots_services.load_hot_spots(session, limit=1),
        spots_services.load_hidden_spots(session, limit=1),
        _safe(load_kto_channel_cached(redis, kto, "festa")),
        _safe(load_kto_channel_cached(redis, kto, "pets")),
        _safe(load_kto_channel_cached(redis, kto, "snap")),
    )
    metas = [ChannelMetaRow("around", CHANNEL_LABELS["around"], None, True)]
    metas.append(_meta_from_rows("hot", hot))
    metas.append(_meta_from_rows("hidden", hidden))
    if festa is None:
        metas.append(ChannelMetaRow("festa", CHANNEL_LABELS["festa"], None, False))
    elif festa:
        metas.append(_meta_from_rows("festa", festa))
    metas.append(_meta_or_unavailable("pets", pets))
    metas.append(_meta_or_unavailable("snap", snap))
    return metas


def _region(card: NearbySpotCard) -> str:
    return " ".join(part for part in (card.regionName, card.sigunguName) if part)
