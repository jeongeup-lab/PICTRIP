from __future__ import annotations

import itertools
import math
from urllib.parse import quote

from app.modules.plan.naver_local import NaverPlace
from app.modules.plan.odsay import transit_minutes
from app.modules.plan.schemas import ExternalLinks, PlanDay, PlanSlot, SlotType, TravelLeg
from app.modules.plan.services.candidates import PlanCandidates
from app.modules.plan.services.intent import PlanIntent
from app.modules.spots.services import NearbySpotRow
from app.web.errors import PlanNotEnoughSpots

_WALK_THRESHOLD_M = 1_200
_WALK_M_PER_MIN = 67.0
_FALLBACK_TRANSIT_M_PER_MIN = 370.0
_FALLBACK_TRANSIT_BASE_MIN = 8
_MAX_ODSAY_CALLS = 10
_ATTRACTIONS_PER_DAY = 2


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _order_by_chain(
    anchor_lat: float, anchor_lng: float, rows: list[NearbySpotRow]
) -> list[NearbySpotRow]:
    coords = {r.content_id: (r.mapy, r.mapx) for r in rows if r.mapy and r.mapx}
    remaining = [r for r in rows if r.content_id in coords]
    ordered: list[NearbySpotRow] = []
    cur_lat, cur_lng = anchor_lat, anchor_lng
    while remaining:
        nearest = min(
            remaining,
            key=lambda r: _haversine_m(cur_lat, cur_lng, *coords[r.content_id]),
        )
        remaining.remove(nearest)
        ordered.append(nearest)
        cur_lat, cur_lng = coords[nearest.content_id]
    return ordered


def _naver_links(name: str, lat: float | None, lng: float | None) -> ExternalLinks:
    naver = f"https://map.naver.com/p/search/{quote(name)}"
    kakao = f"https://map.kakao.com/link/map/{quote(name)},{lat},{lng}" if lat and lng else None
    return ExternalLinks(naver=naver, kakao=kakao)


def _attraction_slot(row: NearbySpotRow, label: str) -> PlanSlot:
    return PlanSlot(
        type="attraction",
        source="kto",
        label=label,
        name=row.title,
        category=row.category,
        contentId=row.content_id,
        address=row.addr1,
        lat=row.mapy,
        lng=row.mapx,
        imageUrl=row.first_image_url,
    )


class _HopBudget:
    def __init__(self, limit: int) -> None:
        self.remaining = limit


async def _leg(prev: PlanSlot, cur: PlanSlot, budget: _HopBudget) -> TravelLeg | None:
    if prev.lat is None or prev.lng is None or cur.lat is None or cur.lng is None:
        return None
    dist = _haversine_m(prev.lat, prev.lng, cur.lat, cur.lng)
    if dist <= _WALK_THRESHOLD_M:
        return TravelLeg(mode="walk", minutes=max(2, round(dist / _WALK_M_PER_MIN)))

    minutes: int | None = None
    if budget.remaining > 0:
        budget.remaining -= 1
        minutes = await transit_minutes(
            from_lat=prev.lat, from_lng=prev.lng, to_lat=cur.lat, to_lng=cur.lng
        )
    if minutes is None:
        minutes = round(dist / _FALLBACK_TRANSIT_M_PER_MIN) + _FALLBACK_TRANSIT_BASE_MIN
    return TravelLeg(mode="transit", minutes=minutes)


async def assemble_days(intent: PlanIntent, cand: PlanCandidates) -> list[PlanDay]:
    day_count = intent.days or 1
    ordered = _order_by_chain(cand.anchor_lat, cand.anchor_lng, cand.attractions)
    if not ordered:
        raise PlanNotEnoughSpots()

    def naver_slot(place: NaverPlace, *, slot_type: SlotType, label: str) -> PlanSlot:
        return PlanSlot(
            type=slot_type,
            source="naver",
            label=label,
            name=place.name,
            category=place.category,
            address=place.address,
            lat=place.lat,
            lng=place.lng,
            imageUrl=cand.food_images.get(place.name),
            links=_naver_links(place.name, place.lat, place.lng),
        )

    meals = list(cand.meals)
    cafes = list(cand.cafes)
    budget = _HopBudget(_MAX_ODSAY_CALLS)
    days: list[PlanDay] = []

    for day_index in range(1, day_count + 1):
        chunk = ordered[(day_index - 1) * _ATTRACTIONS_PER_DAY : day_index * _ATTRACTIONS_PER_DAY]
        if not chunk:
            break

        slots: list[PlanSlot] = []
        if chunk:
            slots.append(_attraction_slot(chunk[0], "오전"))
        if meals:
            slots.append(naver_slot(meals.pop(0), slot_type="meal", label="점심"))
        if len(chunk) > 1:
            slots.append(_attraction_slot(chunk[1], "오후"))
        if cafes:
            slots.append(naver_slot(cafes.pop(0), slot_type="cafe", label="카페"))
        if meals:
            slots.append(naver_slot(meals.pop(0), slot_type="meal", label="저녁"))

        for prev, cur in itertools.pairwise(slots):
            cur.travelFromPrev = await _leg(prev, cur, budget)

        days.append(PlanDay(index=day_index, slots=slots))

    if not days:
        raise PlanNotEnoughSpots()
    return days
