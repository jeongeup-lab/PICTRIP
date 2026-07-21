from __future__ import annotations

from app.core.db import AsyncSession
from app.core.logging import get_logger
from app.kto.client import https_kto_image
from app.modules.plan import repositories
from app.modules.plan.errors import PlanNotFound, PlanSlotInvalid, PlanSpotNotFound
from app.modules.plan.schemas import (
    AlternativesResponse,
    ExtractedPlace,
    PlanEditRequest,
    PlanResponse,
    ResolvedPlace,
    ResolvedSpot,
    ScheduleDay,
    ScheduleSlot,
)
from app.modules.plan.services.assemble import _time_of_day, _travel_minutes
from app.modules.spots.services import NearbyCategory, find_nearby_spots

logger = get_logger(__name__)

ALTERNATIVES_LIMIT = 3
ALTERNATIVES_RADIUS_M = 5_000

_CATEGORY_BY_PLACE_TYPE: dict[str, NearbyCategory] = {
    "attraction": NearbyCategory.attraction,
    "restaurant": NearbyCategory.food,
    "cafe": NearbyCategory.cafe,
}


async def list_alternatives(
    session: AsyncSession, plan_id: int, *, day: int, slot: int
) -> AlternativesResponse:
    response = await _load(session, plan_id)
    target = _get_slot(response, day, slot)
    place = target.place
    category = _CATEGORY_BY_PLACE_TYPE.get(place.extracted.placeType)
    if category is None or place.spot is None or place.spot.lat is None or place.spot.lng is None:
        return AlternativesResponse(alternatives=[])

    used = _used_content_ids(response)
    rows = await find_nearby_spots(
        session,
        lat=place.spot.lat,
        lng=place.spot.lng,
        radius=ALTERNATIVES_RADIUS_M,
        category=category,
    )
    alternatives = [
        ResolvedSpot(
            source="kto",
            contentId=row.content_id,
            title=row.title,
            category=row.category,
            address=row.addr1,
            lat=row.mapy,
            lng=row.mapx,
            imageUrl=https_kto_image(row.first_image_url),
        )
        for row in rows
        if row.content_id not in used and row.mapy is not None and row.mapx is not None
    ]
    return AlternativesResponse(alternatives=alternatives[:ALTERNATIVES_LIMIT])


async def apply_edit(session: AsyncSession, plan_id: int, payload: PlanEditRequest) -> PlanResponse:
    response = await _load(session, plan_id)
    day_index = _day_index(response, payload.day)
    day_obj = response.days[day_index]
    if not 0 <= payload.slot < len(day_obj.slots):
        raise PlanSlotInvalid()

    if payload.op == "remove":
        del day_obj.slots[payload.slot]
        if not day_obj.slots:
            del response.days[day_index]
            for number, remaining in enumerate(response.days, start=1):
                remaining.day = number
        else:
            _rebuild_day(day_obj)
    else:
        if not payload.contentId:
            raise PlanSlotInvalid()
        replacement = await _replacement_place(
            session, payload.contentId, day_obj.slots[payload.slot].place
        )
        day_obj.slots[payload.slot] = ScheduleSlot(
            timeOfDay=day_obj.slots[payload.slot].timeOfDay,
            place=replacement,
        )
        _rebuild_day(day_obj)

    await repositories.set_plan_payload(session, plan_id, response.model_dump(exclude={"planId"}))
    await session.commit()
    response.planId = plan_id
    logger.info("plan.edit.done", plan_id=plan_id, op=payload.op)
    return response


async def _load(session: AsyncSession, plan_id: int) -> PlanResponse:
    payload = await repositories.get_plan_payload(session, plan_id)
    if payload is None:
        raise PlanNotFound()
    response = PlanResponse.model_validate(payload)
    response.planId = plan_id
    return response


def _day_index(response: PlanResponse, day: int) -> int:
    for index, candidate in enumerate(response.days):
        if candidate.day == day:
            return index
    raise PlanSlotInvalid()


def _get_slot(response: PlanResponse, day: int, slot: int) -> ScheduleSlot:
    day_obj = response.days[_day_index(response, day)]
    if not 0 <= slot < len(day_obj.slots):
        raise PlanSlotInvalid()
    return day_obj.slots[slot]


def _used_content_ids(response: PlanResponse) -> set[str]:
    return {
        slot.place.spot.contentId
        for day in response.days
        for slot in day.slots
        if slot.place.spot is not None and slot.place.spot.contentId is not None
    }


async def _replacement_place(
    session: AsyncSession, content_id: str, original: ResolvedPlace
) -> ResolvedPlace:
    brief = await repositories.get_spot_brief(session, content_id)
    if brief is None:
        raise PlanSpotNotFound()
    return ResolvedPlace(
        extracted=ExtractedPlace(
            name=brief.title,
            placeType=original.extracted.placeType,
            regionHint=original.extracted.regionHint,
            orderHint=original.extracted.orderHint,
        ),
        spot=ResolvedSpot(
            source="kto",
            contentId=brief.content_id,
            title=brief.title,
            category=brief.category,
            address=brief.addr1,
            lat=brief.lat,
            lng=brief.lng,
            imageUrl=https_kto_image(brief.image_url),
        ),
        confidence=1.0,
        status="matched",
    )


def _rebuild_day(day_obj: ScheduleDay) -> None:
    total = len(day_obj.slots)
    rebuilt = []
    for index, slot in enumerate(day_obj.slots):
        travel = _travel_minutes(day_obj.slots[index - 1].place, slot.place) if index > 0 else None
        rebuilt.append(
            ScheduleSlot(
                timeOfDay=_time_of_day(index, total),
                place=slot.place,
                travelMinutesFromPrev=travel,
            )
        )
    day_obj.slots = rebuilt
