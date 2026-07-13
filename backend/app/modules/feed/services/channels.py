from __future__ import annotations

from dataclasses import dataclass

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


def _region(card: NearbySpotCard) -> str:
    return " ".join(part for part in (card.regionName, card.sigunguName) if part)
