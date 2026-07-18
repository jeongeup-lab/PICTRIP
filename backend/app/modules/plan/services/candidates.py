from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Literal

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
_FOOD_RADIUS_M = 8_000
_IMAGE_MATCH_RADIUS_M = 300
_IMAGE_MATCH_MIN_RATIO = 0.55
_MEALS_PER_DAY = 2
_CAFES_PER_DAY = 1
_ATTRACTIONS_PER_DAY = 2
_NAVER_MAX_DISPLAY = 5
_MEAL_EXCLUDE_KEYWORDS = ("카페", "디저트", "베이커리", "간식", "찻집", "분식", "닭강정")
_CAFE_INCLUDE_KEYWORDS = ("카페", "커피", "디저트", "베이커리", "찻집")
_FOOD_MAX_KM_FROM_ANCHOR = 15.0

FoodSource = Literal["naver", "kto"]


@dataclass
class FoodCandidate:
    name: str
    category: str | None
    address: str | None
    lat: float | None
    lng: float | None
    source: FoodSource
    content_id: str | None = None
    image_url: str | None = None


@dataclass
class PlanCandidates:
    anchor_lat: float
    anchor_lng: float
    attractions: list[NearbySpotRow]
    meals: list[FoodCandidate]
    cafes: list[FoodCandidate]


def _name_ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, a.replace(" ", ""), b.replace(" ", "")).ratio()


def _is_meal_place(place: NaverPlace) -> bool:
    category = place.category or ""
    return not any(k in category for k in _MEAL_EXCLUDE_KEYWORDS)


def _is_cafe_place(place: NaverPlace) -> bool:
    category = place.category or ""
    return any(k in category for k in _CAFE_INCLUDE_KEYWORDS)


def _km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(a))


def _to_candidate(place: NaverPlace) -> FoodCandidate:
    return FoodCandidate(
        name=place.name,
        category=place.category,
        address=place.address,
        lat=place.lat,
        lng=place.lng,
        source="naver",
    )


def _row_to_candidate(row: NearbySpotRow) -> FoodCandidate:
    return FoodCandidate(
        name=row.title,
        category=row.category,
        address=row.addr1,
        lat=row.mapy,
        lng=row.mapx,
        source="kto",
        content_id=row.content_id,
        image_url=row.first_image_url,
    )


def _locality_from(attractions: list[NearbySpotRow]) -> str | None:
    counts: dict[str, int] = {}
    for row in attractions[:10]:
        parts = (row.addr1 or "").split()
        if len(parts) >= 2 and parts[1].endswith(("시", "군", "구")):
            counts[parts[1]] = counts.get(parts[1], 0) + 1
    if not counts:
        return None
    return max(counts, key=lambda k: counts[k])


def prepare_food(
    meals_raw: list[NaverPlace],
    cafes_raw: list[NaverPlace],
    *,
    anchor_lat: float,
    anchor_lng: float,
) -> tuple[list[FoodCandidate], list[FoodCandidate]]:
    def survives(place: NaverPlace) -> bool:
        return (
            place.lat is not None
            and place.lng is not None
            and _km(anchor_lat, anchor_lng, place.lat, place.lng) <= _FOOD_MAX_KM_FROM_ANCHOR
        )

    def dedupe(cands: list[FoodCandidate]) -> list[FoodCandidate]:
        seen: set[str] = set()
        out: list[FoodCandidate] = []
        for c in cands:
            if c.name not in seen:
                seen.add(c.name)
                out.append(c)
        return out

    def by_anchor_dist(c: FoodCandidate) -> float:
        if c.lat is None or c.lng is None:
            return _FOOD_MAX_KM_FROM_ANCHOR
        return _km(anchor_lat, anchor_lng, c.lat, c.lng)

    meals = dedupe([_to_candidate(p) for p in meals_raw if _is_meal_place(p) and survives(p)])
    meal_names = {c.name for c in meals}
    cafes = dedupe(
        [
            _to_candidate(p)
            for p in cafes_raw
            if _is_cafe_place(p) and p.name not in meal_names and survives(p)
        ]
    )
    meals.sort(key=by_anchor_dist)
    cafes.sort(key=by_anchor_dist)
    return meals, cafes


async def _attach_kto_images(
    session: AsyncSession, cands: list[FoodCandidate], category: NearbyCategory
) -> None:
    for cand in cands:
        if cand.image_url or cand.lat is None or cand.lng is None:
            continue
        rows = await find_nearby_spots(
            session,
            lat=cand.lat,
            lng=cand.lng,
            radius=_IMAGE_MATCH_RADIUS_M,
            category=category,
        )
        best: tuple[float, str] | None = None
        for row in rows:
            if not row.first_image_url:
                continue
            ratio = _name_ratio(cand.name, row.title)
            if ratio >= _IMAGE_MATCH_MIN_RATIO and (best is None or ratio > best[0]):
                best = (ratio, row.first_image_url)
        if best:
            cand.image_url = best[1]


async def _kto_food_fallback(
    session: AsyncSession,
    *,
    anchor_lat: float,
    anchor_lng: float,
    category: NearbyCategory,
    exclude_names: set[str],
    limit: int,
) -> list[FoodCandidate]:
    if limit <= 0:
        return []
    rows = await find_nearby_spots(
        session,
        lat=anchor_lat,
        lng=anchor_lng,
        radius=_FOOD_RADIUS_M,
        category=category,
    )
    out: list[FoodCandidate] = []
    for row in rows:
        if not row.first_image_url:
            continue
        if any(_name_ratio(row.title, name) >= _IMAGE_MATCH_MIN_RATIO for name in exclude_names):
            continue
        out.append(_row_to_candidate(row))
        if len(out) >= limit:
            break
    return out


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

    meals_raw, cafes_raw = await asyncio.gather(
        search_local(f"{region} 맛집", display=_NAVER_MAX_DISPLAY),
        search_local(f"{region} 카페", display=_NAVER_MAX_DISPLAY),
    )
    if len([p for p in meals_raw if _is_meal_place(p)]) < days * _MEALS_PER_DAY:
        meals_raw = meals_raw + await search_local(f"{region} 밥집", display=_NAVER_MAX_DISPLAY)

    locality = _locality_from(attractions)
    if locality and locality not in region:
        extra_meals, extra_cafes = await asyncio.gather(
            search_local(f"{locality} 맛집", display=_NAVER_MAX_DISPLAY),
            search_local(f"{locality} 카페", display=_NAVER_MAX_DISPLAY),
        )
        meals_raw = meals_raw + extra_meals
        cafes_raw = cafes_raw + extra_cafes

    meals, cafes = prepare_food(meals_raw, cafes_raw, anchor_lat=anchor_lat, anchor_lng=anchor_lng)
    await _attach_kto_images(session, meals, NearbyCategory.food)
    await _attach_kto_images(session, cafes, NearbyCategory.cafe)

    naver_meal_count, naver_cafe_count = len(meals), len(cafes)
    meals.extend(
        await _kto_food_fallback(
            session,
            anchor_lat=anchor_lat,
            anchor_lng=anchor_lng,
            category=NearbyCategory.food,
            exclude_names={c.name for c in meals},
            limit=days * _MEALS_PER_DAY,
        )
    )
    cafes.extend(
        await _kto_food_fallback(
            session,
            anchor_lat=anchor_lat,
            anchor_lng=anchor_lng,
            category=NearbyCategory.cafe,
            exclude_names={c.name for c in cafes},
            limit=days * _CAFES_PER_DAY,
        )
    )

    logger.info(
        "plan.candidates.collected",
        region=region,
        locality=locality,
        attractions=len(attractions),
        meals=len(meals),
        cafes=len(cafes),
        naver_meals=naver_meal_count,
        naver_cafes=naver_cafe_count,
    )
    return PlanCandidates(
        anchor_lat=anchor_lat,
        anchor_lng=anchor_lng,
        attractions=attractions,
        meals=meals,
        cafes=cafes,
    )
