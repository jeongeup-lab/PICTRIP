"""Home feed assembly — 6 region heroes + 3 mood rails (S07 §3).

Backend-assembled feed: the 6 published ``type='region'`` curations (ordered by
``position``) become heroes, and the 3 published ``type='mood'`` curations become
rails. Each rail carries up to 8 resolved ``SpotCardRow``s (handpicked or the
quality-gate random pool, see ``curations.resolve_curation_spots``).
"""

from __future__ import annotations

from dataclasses import dataclass

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.spots.models import Spot
from app.modules.spots.services import curations as curation_svc
from app.modules.spots.services.cards import load_congestion
from app.modules.spots.services.rows import SpotCardRow

_HERO_COUNT = 6
_RAIL_COUNT = 3


@dataclass
class HeroRow:
    id: int
    slug: str
    title: str
    subtitle: str | None
    cover_url: str | None


@dataclass
class RailRow:
    id: int
    title: str
    subtitle: str | None
    spots: list[SpotCardRow]


@dataclass
class HomeFeedRow:
    heroes: list[HeroRow]
    rails: list[RailRow]


async def _cover_url(
    session: AsyncSession,
    cover_spot_id: str | None,
    resolved: list[SpotCardRow],
) -> str | None:
    """coverUrl = cover spot's firstImageUrl, else first resolved spot's, else null."""
    if cover_spot_id is not None:
        img = (
            await session.execute(
                select(Spot.first_image_url).where(Spot.content_id == cover_spot_id)
            )
        ).scalar_one_or_none()
        if img:
            return img
    for r in resolved:
        if r.first_image_url:
            return r.first_image_url
    return None


async def assemble_home_feed(session: AsyncSession, redis: Redis) -> HomeFeedRow:
    region_curations = await curation_svc.list_published_curations(session, "region")
    mood_curations = await curation_svc.list_published_curations(session, "mood")

    heroes: list[HeroRow] = []
    for cur in region_curations[:_HERO_COUNT]:
        resolved = await curation_svc.resolve_curation_spots(session, redis, cur)
        heroes.append(
            HeroRow(
                id=cur.id,
                slug=cur.slug,
                title=cur.title,
                subtitle=cur.subtitle,
                cover_url=await _cover_url(session, cur.cover_spot_id, resolved),
            )
        )

    rails: list[RailRow] = []
    for cur in mood_curations[:_RAIL_COUNT]:
        resolved = await curation_svc.resolve_curation_spots(session, redis, cur)
        congestion = await load_congestion(session, [r.content_id for r in resolved])
        for r in resolved:
            r.congestion = congestion.get(r.content_id)
        rails.append(RailRow(id=cur.id, title=cur.title, subtitle=cur.subtitle, spots=resolved))

    return HomeFeedRow(heroes=heroes, rails=rails)
