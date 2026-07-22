from __future__ import annotations

import math
from collections import Counter
from itertools import permutations

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
from app.modules.plan.services.geo import haversine_km
from app.modules.plan.services.titles import plan_title

logger = get_logger(__name__)

TARGET_SLOTS_PER_DAY = 4
MAX_SLOTS_PER_DAY = 5
MAX_DAYS = 7
WALK_MAX_KM = 1.2
WALK_MINUTES_PER_KM = 12.0
DRIVE_BASE_MINUTES = 5.0
DRIVE_MINUTES_PER_KM = 2.0
DAY_BALANCE_WEIGHT_KM = 4.0
REGION_SPLIT_PENALTY_KM = 30.0
FIRST_SLOT_MEAL_PENALTY_KM = 6.0
ADJACENT_MEAL_PENALTY_KM = 4.0
CAFE_BEFORE_MEAL_PENALTY_KM = 3.0
DINNER_LAST_PENALTY_KM = 5.0
LUNCH_SLOT_INDEX = 1


async def build_schedule(session: AsyncSession, payload: AssembleRequest) -> PlanResponse:
    placed, unplaced = _split_placeable(payload.places)
    if not placed:
        raise PlanNoPlacesFound("일정에 넣을 수 있는 장소가 없습니다. 장소를 다시 선택해 주세요.")
    ordered = _order_places(placed)
    days_count = payload.days or _infer_days(len(ordered))
    days_count = min(days_count, MAX_DAYS, len(ordered))
    capacity = days_count * MAX_SLOTS_PER_DAY
    overflow = ordered[capacity:]
    chunks = _partition_days(ordered[:capacity], days_count)
    days: list[ScheduleDay] = []
    previous_last: ResolvedPlace | None = None
    for index, chunk in enumerate(chunks):
        day = _build_day(index + 1, chunk, previous_last, pin_first=index == 0 and payload.pinFirst)
        days.append(day)
        previous_last = day.slots[-1].place
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
    response.planId = plan.public_id
    logger.info(
        "plan.assemble.done",
        plan_id=plan.public_id,
        days=days_count,
        placed=len(ordered),
        unplaced=len(response.unplaced),
    )
    return response


async def load_plan(session: AsyncSession, plan_id: str) -> PlanResponse:
    plan = await repositories.get_plan(session, plan_id)
    if plan is None:
        raise PlanNotFound()
    response = PlanResponse.model_validate(plan.payload)
    response.planId = plan.public_id
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


def _coords(place: ResolvedPlace) -> tuple[float, float] | None:
    if place.spot is None or place.spot.lat is None or place.spot.lng is None:
        return None
    return place.spot.lat, place.spot.lng


def _infer_days(place_count: int) -> int:
    return max(1, math.ceil(place_count / TARGET_SLOTS_PER_DAY))


def _partition_days(places: list[ResolvedPlace], days_count: int) -> list[list[ResolvedPlace]]:
    total = len(places)
    if days_count <= 1:
        return [places]
    ideal = total / days_count
    best = [[math.inf] * (days_count + 1) for _ in range(total + 1)]
    split_at = [[0] * (days_count + 1) for _ in range(total + 1)]
    best[0][0] = 0.0
    for end in range(1, total + 1):
        for day in range(1, days_count + 1):
            for start in range(max(day - 1, end - MAX_SLOTS_PER_DAY), end):
                previous = best[start][day - 1]
                if math.isinf(previous):
                    continue
                cost = previous + _cut_penalty(places, start) + _day_cost(places[start:end], ideal)
                if cost < best[end][day]:
                    best[end][day] = cost
                    split_at[end][day] = start
    bounds: list[tuple[int, int]] = []
    end = total
    for day in range(days_count, 0, -1):
        start = split_at[end][day]
        bounds.append((start, end))
        end = start
    return [places[start:end] for start, end in reversed(bounds)]


def _cut_penalty(places: list[ResolvedPlace], index: int) -> float:
    if index == 0:
        return 0.0
    before = _region_label(places[index - 1])
    after = _region_label(places[index])
    if before and before == after:
        return REGION_SPLIT_PENALTY_KM
    return 0.0


def _day_cost(chunk: list[ResolvedPlace], ideal: float) -> float:
    return DAY_BALANCE_WEIGHT_KM * (len(chunk) - ideal) ** 2 + _spread_km(chunk)


def _spread_km(places: list[ResolvedPlace]) -> float:
    coords = [c for place in places if (c := _coords(place))]
    if len(coords) < 2:
        return 0.0
    return max(
        haversine_km(a[0], a[1], b[0], b[1]) for i, a in enumerate(coords) for b in coords[i + 1 :]
    )


def _build_day(
    day_number: int,
    places: list[ResolvedPlace],
    previous_last: ResolvedPlace | None,
    *,
    pin_first: bool = False,
) -> ScheduleDay:
    ordered = _day_order(places, previous_last, pin_first=pin_first)
    slots = []
    for index, place in enumerate(ordered):
        travel = _travel_minutes(ordered[index - 1], place) if index > 0 else None
        slots.append(
            ScheduleSlot(
                timeOfDay=_time_of_day(index, len(ordered)),
                place=place,
                travelMinutesFromPrev=travel,
            )
        )
    return ScheduleDay(
        day=day_number,
        regionLabel=_majority_region(ordered),
        slots=slots,
    )


def _majority_region(places: list[ResolvedPlace]) -> str | None:
    counts = Counter(label for place in places if (label := _region_label(place)))
    if not counts:
        return None
    return counts.most_common(1)[0][0]


def _day_order(
    places: list[ResolvedPlace], previous_last: ResolvedPlace | None, *, pin_first: bool = False
) -> list[ResolvedPlace]:
    lodgings = [p for p in places if p.extracted.placeType == "hotel"]
    others = [p for p in places if p.extracted.placeType != "hotel"]
    if len(others) <= 1 or any(_coords(place) is None for place in others):
        return others + lodgings
    anchor = _coords(previous_last) if previous_last is not None else None
    if pin_first:
        head, tail = others[:1], others[1:]
        orders = [(*head, *rest) for rest in permutations(tail)]
    else:
        orders = list(permutations(others))
    in_rhythm = [order for order in orders if _rhythm_ok(order)]
    best_order = others + lodgings
    best_cost = math.inf
    for candidate in in_rhythm or orders:
        sequence = [*candidate, *lodgings]
        cost = _sequence_cost(sequence, anchor)
        if cost < best_cost:
            best_cost = cost
            best_order = sequence
    return best_order


def _rhythm_ok(order: tuple[ResolvedPlace, ...]) -> bool:
    types = [place.extracted.placeType for place in order]
    if "attraction" in types and types[0] != "attraction":
        return False
    if "restaurant" in types:
        if types[-1] != "restaurant":
            return False
        if "cafe" in types and types.index("cafe") < types.index("restaurant"):
            return False
        meals = [index for index, place_type in enumerate(types) if place_type == "restaurant"]
        if len(meals) >= 2 and meals[0] != LUNCH_SLOT_INDEX:
            return False
    for index in range(1, len(types)):
        if types[index] in ("restaurant", "cafe") and types[index] == types[index - 1]:
            return False
    return True


def _sequence_cost(sequence: list[ResolvedPlace], anchor: tuple[float, float] | None) -> float:
    cost = _type_penalty(sequence)
    prev = anchor
    for place in sequence:
        current = _coords(place)
        if prev is not None and current is not None:
            cost += haversine_km(prev[0], prev[1], current[0], current[1])
        if current is not None:
            prev = current
    return cost


def _type_penalty(sequence: list[ResolvedPlace]) -> float:
    types = [p.extracted.placeType for p in sequence if p.extracted.placeType != "hotel"]
    if not types:
        return 0.0
    penalty = 0.0
    if types[0] in ("restaurant", "cafe"):
        penalty += FIRST_SLOT_MEAL_PENALTY_KM
    for index, place_type in enumerate(types):
        if index > 0 and place_type in ("restaurant", "cafe") and place_type == types[index - 1]:
            penalty += ADJACENT_MEAL_PENALTY_KM
        if place_type == "cafe" and "restaurant" not in types[:index]:
            penalty += CAFE_BEFORE_MEAL_PENALTY_KM
    if "restaurant" in types and types[-1] != "restaurant":
        penalty += DINNER_LAST_PENALTY_KM
    return penalty


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
    distance_km = haversine_km(lat1, lng1, lat2, lng2)
    if distance_km <= WALK_MAX_KM:
        minutes = distance_km * WALK_MINUTES_PER_KM
    else:
        minutes = DRIVE_BASE_MINUTES + distance_km * DRIVE_MINUTES_PER_KM
    return max(1, round(minutes))
