from __future__ import annotations

from app.core.db import AsyncSession
from app.core.logging import get_logger
from app.kto.client import https_kto_image
from app.modules.plan import repositories
from app.modules.plan.errors import PlanNotEnoughSpots, PlanSpotNotFound
from app.modules.plan.schemas import (
    AssembleRequest,
    ExtractedPlace,
    FromSpotRequest,
    PlaceType,
    PlanResponse,
    ResolvedPlace,
    ResolvedSpot,
)
from app.modules.plan.services import assemble
from app.modules.spots.services import NearbyCategory, NearbySpotRow, find_nearby_spots

logger = get_logger(__name__)

CANDIDATE_RADIUS_M = 15_000
ATTRACTIONS_PER_DAY = 2
FOOD_PER_DAY = 1
CAFE_PER_DAY = 1
MIN_SLOTS_PER_DAY = 2

_DAY_PATTERN: tuple[PlaceType, ...] = ("attraction", "restaurant", "attraction", "cafe")


async def build_from_spot(session: AsyncSession, payload: FromSpotRequest) -> PlanResponse:
    seed = await repositories.get_spot_brief(session, payload.contentId)
    if seed is None or seed.lat is None or seed.lng is None:
        raise PlanSpotNotFound()

    attractions = await _candidates(
        session,
        lat=seed.lat,
        lng=seed.lng,
        exclude=seed.content_id,
        category=NearbyCategory.attraction,
    )
    foods = await _candidates(
        session,
        lat=seed.lat,
        lng=seed.lng,
        exclude=seed.content_id,
        category=NearbyCategory.food,
    )
    cafes = await _candidates(
        session,
        lat=seed.lat,
        lng=seed.lng,
        exclude=seed.content_id,
        category=NearbyCategory.cafe,
    )

    pools: dict[PlaceType, list[ResolvedPlace]] = {
        "attraction": [_seed_place(seed), *attractions],
        "restaurant": foods,
        "cafe": cafes,
    }
    ordered = _interleave(pools, days=payload.days)
    if len(ordered) < payload.days * MIN_SLOTS_PER_DAY:
        raise PlanNotEnoughSpots()

    response = await assemble.build_schedule(
        session,
        AssembleRequest(places=ordered, days=payload.days, sourceKind="photo"),
    )
    logger.info(
        "plan.from_spot.done",
        seed=seed.content_id,
        days=payload.days,
        placed=len(ordered),
    )
    return response


async def _candidates(
    session: AsyncSession,
    *,
    lat: float,
    lng: float,
    exclude: str,
    category: NearbyCategory,
) -> list[ResolvedPlace]:
    rows = await find_nearby_spots(
        session, lat=lat, lng=lng, radius=CANDIDATE_RADIUS_M, category=category
    )
    place_type = _place_type(category)
    return [
        _row_place(row, place_type)
        for row in rows
        if row.content_id != exclude and row.mapy is not None and row.mapx is not None
    ]


def _place_type(category: NearbyCategory) -> PlaceType:
    if category is NearbyCategory.food:
        return "restaurant"
    if category is NearbyCategory.cafe:
        return "cafe"
    return "attraction"


def _interleave(pools: dict[PlaceType, list[ResolvedPlace]], *, days: int) -> list[ResolvedPlace]:
    queues = {place_type: list(places) for place_type, places in pools.items()}
    ordered: list[ResolvedPlace] = []
    for _ in range(days):
        for place_type in _DAY_PATTERN:
            place = _pop(queues, place_type)
            if place is not None:
                ordered.append(place)
    for index, place in enumerate(ordered):
        place.extracted.orderHint = index + 1
    return ordered


def _pop(
    queues: dict[PlaceType, list[ResolvedPlace]], place_type: PlaceType
) -> ResolvedPlace | None:
    queue = queues.get(place_type)
    if queue:
        return queue.pop(0)
    fallback = queues.get("attraction")
    if place_type != "attraction" and fallback:
        return fallback.pop(0)
    return None


def _seed_place(seed: repositories.SpotBrief) -> ResolvedPlace:
    return ResolvedPlace(
        extracted=ExtractedPlace(
            name=seed.title,
            placeType="attraction",
            regionHint=_region_label(seed.addr1),
        ),
        spot=ResolvedSpot(
            source="kto",
            contentId=seed.content_id,
            title=seed.title,
            category=seed.category,
            address=seed.addr1,
            lat=seed.lat,
            lng=seed.lng,
            imageUrl=https_kto_image(seed.image_url),
        ),
        confidence=1.0,
        status="matched",
    )


def _row_place(row: NearbySpotRow, place_type: PlaceType) -> ResolvedPlace:
    return ResolvedPlace(
        extracted=ExtractedPlace(
            name=row.title,
            placeType=place_type,
            regionHint=_region_label(row.addr1),
        ),
        spot=ResolvedSpot(
            source="kto",
            contentId=row.content_id,
            title=row.title,
            category=row.category,
            address=row.addr1,
            lat=row.mapy,
            lng=row.mapx,
            imageUrl=https_kto_image(row.first_image_url),
        ),
        confidence=1.0,
        status="matched",
    )


def _region_label(addr1: str | None) -> str | None:
    if not addr1:
        return None
    tokens = addr1.split()
    return " ".join(tokens[:2]) if tokens else None
