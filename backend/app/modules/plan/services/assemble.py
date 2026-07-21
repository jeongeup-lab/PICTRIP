from __future__ import annotations

import math

from app.core.db import AsyncSession
from app.core.logging import get_logger
from app.modules.plan import repositories
from app.modules.plan.errors import PlanNoPlacesFound, PlanNotFound
from app.modules.plan.schemas import (
    AssembleRequest,
    PlanResponse,
    ResolvedPlace,
    ScheduleDay,
    ScheduleSlot,
    TimeOfDay,
)
from app.modules.plan.services.titles import plan_title

logger = get_logger(__name__)

TARGET_SLOTS_PER_DAY = 4
MAX_SLOTS_PER_DAY = 5
MAX_DAYS = 7
WALK_MAX_KM = 1.2
WALK_MINUTES_PER_KM = 12.0
DRIVE_BASE_MINUTES = 5.0
DRIVE_MINUTES_PER_KM = 2.0


async def build_schedule(session: AsyncSession, payload: AssembleRequest) -> PlanResponse:
    placed, unplaced = _split_placeable(payload.places)
    if not placed:
        raise PlanNoPlacesFound("일정에 넣을 수 있는 장소가 없습니다. 장소를 다시 선택해 주세요.")
    ordered = _order_places(placed)
    days_count = payload.days or _infer_days(len(ordered))
    days_count = min(days_count, MAX_DAYS, len(ordered))
    capacity = days_count * MAX_SLOTS_PER_DAY
    overflow = ordered[capacity:]
    days = [
        _build_day(index + 1, chunk)
        for index, chunk in enumerate(_chunk(ordered[:capacity], days_count))
    ]
    response = PlanResponse(
        sourceTitle=plan_title(ordered, days_count) or payload.sourceTitle,
        sourceUrl=payload.sourceUrl,
        days=days,
        unplaced=unplaced + overflow,
    )
    plan = await repositories.create_plan(
        session,
        source_kind=payload.sourceKind,
        source_url=payload.sourceUrl,
        source_title=payload.sourceTitle,
        payload=response.model_dump(exclude={"planId"}),
    )
    await session.commit()
    response.planId = plan.id
    logger.info(
        "plan.assemble.done",
        plan_id=plan.id,
        days=days_count,
        placed=len(ordered),
        unplaced=len(response.unplaced),
    )
    return response


async def load_plan(session: AsyncSession, plan_id: int) -> PlanResponse:
    plan = await repositories.get_plan(session, plan_id)
    if plan is None:
        raise PlanNotFound()
    response = PlanResponse.model_validate(plan.payload)
    response.planId = plan.id
    return response


def _split_placeable(
    places: list[ResolvedPlace],
) -> tuple[list[ResolvedPlace], list[ResolvedPlace]]:
    placed = []
    unplaced = []
    for place in places:
        if place.spot is not None and place.status in ("matched", "ambiguous", "naver_only"):
            placed.append(place)
        elif place.extracted.placeType != "region":
            unplaced.append(place)
    return placed, unplaced


def _order_places(places: list[ResolvedPlace]) -> list[ResolvedPlace]:
    in_content_order = sorted(
        places,
        key=lambda p: p.extracted.orderHint if p.extracted.orderHint is not None else 10_000,
    )
    region_order: list[str] = []
    for place in in_content_order:
        region = _region_label(place)
        if region not in region_order:
            region_order.append(region)
    return sorted(in_content_order, key=lambda p: region_order.index(_region_label(p)))


def _region_label(place: ResolvedPlace) -> str:
    address = place.spot.address if place.spot else None
    if not address:
        return ""
    return " ".join(address.split()[:2])


def _infer_days(place_count: int) -> int:
    return max(1, math.ceil(place_count / TARGET_SLOTS_PER_DAY))


def _chunk(places: list[ResolvedPlace], days_count: int) -> list[list[ResolvedPlace]]:
    total = len(places)
    base = total // days_count
    remainder = total % days_count
    chunks = []
    start = 0
    for index in range(days_count):
        size = base + (1 if index < remainder else 0)
        chunks.append(places[start : start + size])
        start += size
    return [chunk for chunk in chunks if chunk]


def _route_order(places: list[ResolvedPlace]) -> list[ResolvedPlace]:
    coords = []
    for place in places:
        if place.spot is None or place.spot.lat is None or place.spot.lng is None:
            return places
        coords.append((place.spot.lat, place.spot.lng))
    remaining = list(range(1, len(places)))
    route = [0]
    while remaining:
        last = coords[route[-1]]
        nearest = min(
            remaining,
            key=lambda i: _haversine_km(last[0], last[1], coords[i][0], coords[i][1]),
        )
        route.append(nearest)
        remaining.remove(nearest)
    return [places[i] for i in route]


def _build_day(day_number: int, places: list[ResolvedPlace]) -> ScheduleDay:
    places = _route_order(places)
    slots = []
    for index, place in enumerate(places):
        travel = _travel_minutes(places[index - 1], place) if index > 0 else None
        slots.append(
            ScheduleSlot(
                timeOfDay=_time_of_day(index, len(places)),
                place=place,
                travelMinutesFromPrev=travel,
            )
        )
    return ScheduleDay(
        day=day_number,
        regionLabel=_region_label(places[0]) or None,
        slots=slots,
    )


def _time_of_day(index: int, total: int) -> TimeOfDay:
    if index == 0:
        return "morning"
    if total >= 3 and index == total - 1:
        return "evening"
    return "afternoon"


def _travel_minutes(prev: ResolvedPlace, current: ResolvedPlace) -> int | None:
    if prev.spot is None or current.spot is None:
        return None
    lat1, lng1 = prev.spot.lat, prev.spot.lng
    lat2, lng2 = current.spot.lat, current.spot.lng
    if lat1 is None or lng1 is None or lat2 is None or lng2 is None:
        return None
    distance_km = _haversine_km(lat1, lng1, lat2, lng2)
    if distance_km <= WALK_MAX_KM:
        minutes = distance_km * WALK_MINUTES_PER_KM
    else:
        minutes = DRIVE_BASE_MINUTES + distance_km * DRIVE_MINUTES_PER_KM
    return max(1, round(minutes))


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius_km = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * radius_km * math.asin(math.sqrt(a))
