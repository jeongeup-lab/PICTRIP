"""Home feed assembly — 6 region heroes + 3 mood rails (S07 §3)."""

from __future__ import annotations

from dataclasses import dataclass

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.spots.services import curations as curation_svc
from app.modules.spots.services.cards import (
    load_active_spot_cards_by_ids,
    load_cover_images,
)
from app.modules.spots.services.rows import SpotCardRow

_HERO_COUNT = 6
_RAIL_COUNT = 3
_RAIL_MIN_SPOTS = 3  # a rail with fewer resolved spots is omitted (S02:36, S11 §6)


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


def _pick_cover(
    cover_spot_id: str | None,
    cover_images: dict[str, str | None],
    resolved: list[SpotCardRow],
) -> str | None:
    """coverUrl = cover spot's image, else first resolved spot's, else None."""
    if cover_spot_id is not None:
        img = cover_images.get(cover_spot_id)
        if img:
            return img
    for r in resolved:
        if r.first_image_url:
            return r.first_image_url
    return None


async def assemble_home_feed(session: AsyncSession, redis: Redis) -> HomeFeedRow:
    region_curations = (await curation_svc.list_published_curations(session, "region"))[
        :_HERO_COUNT
    ]
    mood_curations = (await curation_svc.list_published_curations(session, "mood"))[:_RAIL_COUNT]

    # Resolve ids per curation (Redis-cached; a cold miss is one light query each),
    # then hydrate every curation's cards / covers in one batched query apiece
    # instead of per-curation — the cold feed's serial DB round-trips drop from
    # ~30 to a handful.
    hero_ids = [
        await curation_svc.resolve_curation_ids(session, redis, c) for c in region_curations
    ]
    rail_ids = [await curation_svc.resolve_curation_ids(session, redis, c) for c in mood_curations]

    all_ids = {cid for ids in (*hero_ids, *rail_ids) for cid in ids}
    # Active-only hydration: a spot hidden after the day-cache was built must
    # not render even while its id is still cached.
    by_id = await load_active_spot_cards_by_ids(session, list(all_ids))
    cover_images = await load_cover_images(
        session, [c.cover_spot_id for c in region_curations if c.cover_spot_id]
    )

    heroes: list[HeroRow] = []
    for cur, ids in zip(region_curations, hero_ids, strict=True):
        resolved = [by_id[cid] for cid in ids if cid in by_id]
        cover = _pick_cover(cur.cover_spot_id, cover_images, resolved)
        if cover is None:
            # Defense rule (S02:36): a hero without a resolvable cover is
            # dropped — fewer than 6 heroes is allowed.
            continue
        heroes.append(
            HeroRow(
                id=cur.id,
                slug=cur.slug,
                title=cur.title,
                subtitle=cur.subtitle,
                cover_url=cover,
            )
        )

    rails: list[RailRow] = []
    for cur, ids in zip(mood_curations, rail_ids, strict=True):
        resolved = [by_id[cid] for cid in ids if cid in by_id]
        if len(resolved) < _RAIL_MIN_SPOTS:
            # Defense rule (S11 §6): omit rails that resolve to fewer than 3 spots.
            continue
        rails.append(RailRow(id=cur.id, title=cur.title, subtitle=cur.subtitle, spots=resolved))

    return HomeFeedRow(heroes=heroes, rails=rails)
