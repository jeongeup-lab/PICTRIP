from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from app.core.db import AsyncSession
from app.core.logging import get_logger
from app.modules.map.services import search_place
from app.modules.plan.naver_local import NaverPlace, search_local
from app.modules.plan.services.intent import PlanIntent
from app.modules.spots.services import NearbyCategory, NearbySpotRow, find_nearby_spots
from app.web.errors import PlanRegionNotFound

logger = get_logger(__name__)

_ATTRACTION_RADIUS_M = 10_000
_ATTRACTION_RADIUS_WIDE_M = 20_000
_IMAGE_MATCH_RADIUS_M = 300
_IMAGE_MATCH_MIN_RATIO = 0.55
_MEALS_PER_DAY = 2
_CAFES_PER_DAY = 1
_ATTRACTIONS_PER_DAY = 2


@dataclass
class PlanCandidates:
    anchor_lat: float
    anchor_lng: float
    attractions: list[NearbySpotRow]
    meals: list[NaverPlace]
    cafes: list[NaverPlace]
    food_images: dict[str, str] = field(default_factory=dict)


def _name_ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, a.replace(" ", ""), b.replace(" ", "")).ratio()


async def _match_food_image(
    session: AsyncSession, place: NaverPlace, category: NearbyCategory
) -> str | None:
    if place.lat is None or place.lng is None:
        return None
    rows = await find_nearby_spots(
        session,
        lat=place.lat,
        lng=place.lng,
        radius=_IMAGE_MATCH_RADIUS_M,
        category=category,
    )
    best: tuple[float, str] | None = None
    for row in rows:
        if not row.first_image_url:
            continue
        ratio = _name_ratio(place.name, row.title)
        if ratio >= _IMAGE_MATCH_MIN_RATIO and (best is None or ratio > best[0]):
            best = (ratio, row.first_image_url)
    return best[1] if best else None


async def collect_candidates(session: AsyncSession, intent: PlanIntent) -> PlanCandidates:
    region = intent.region or ""
    anchor = await search_place(region)
    if anchor is None:
        raise PlanRegionNotFound()
    anchor_lat, anchor_lng = anchor

    days = intent.days or 1
    needed = days * _ATTRACTIONS_PER_DAY + 1

    attractions = await find_nearby_spots(
        session,
        lat=anchor_lat,
        lng=anchor_lng,
        radius=_ATTRACTION_RADIUS_M,
        category=NearbyCategory.attraction,
    )
    attractions = [r for r in attractions if r.first_image_url]
    if len(attractions) < needed:
        wide = await find_nearby_spots(
            session,
            lat=anchor_lat,
            lng=anchor_lng,
            radius=_ATTRACTION_RADIUS_WIDE_M,
            category=NearbyCategory.attraction,
        )
        seen = {r.content_id for r in attractions}
        attractions.extend(r for r in wide if r.first_image_url and r.content_id not in seen)

    meals, cafes = await asyncio.gather(
        search_local(f"{region} 맛집", display=days * _MEALS_PER_DAY + 1),
        search_local(f"{region} 카페", display=days * _CAFES_PER_DAY + 1),
    )

    food_images: dict[str, str] = {}
    for place, category in [(p, NearbyCategory.food) for p in meals] + [
        (p, NearbyCategory.cafe) for p in cafes
    ]:
        url = await _match_food_image(session, place, category)
        if url:
            food_images[place.name] = url

    logger.info(
        "plan.candidates.collected",
        region=region,
        attractions=len(attractions),
        meals=len(meals),
        cafes=len(cafes),
        food_images=len(food_images),
    )
    return PlanCandidates(
        anchor_lat=anchor_lat,
        anchor_lng=anchor_lng,
        attractions=attractions,
        meals=meals,
        cafes=cafes,
        food_images=food_images,
    )
