from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass

import httpx

from app.core.db import AsyncSession
from app.core.logging import get_logger
from app.kto.client import https_kto_image
from app.modules.plan import naver, repositories
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
from app.modules.plan.services.chains import is_chain_branch
from app.modules.plan.services.geo import haversine_km, is_near_duplicate
from app.modules.plan.services.titles import short_region
from app.modules.spots.services import (
    NearbyCategory,
    NearbySpotRow,
    find_nearby_spots,
    load_concentration_rates,
)

logger = get_logger(__name__)

CANDIDATE_RADIUS_M = 15_000
MIN_SLOTS_PER_DAY = 2
POPULARITY_MAX_KM = 8.0
CATEGORY_REPEAT_PENALTY_KM = 3.0
NAVER_POPULAR_BONUS_KM = 8.0
NAVER_MATCH_MAX_KM = 0.7
NAVER_DISPLAY = 5
SEED_SCORE = -math.inf

_DAY_PATTERN: tuple[PlaceType, ...] = (
    "attraction",
    "restaurant",
    "cafe",
    "attraction",
    "restaurant",
)
_CANDIDATE_CATEGORIES = (NearbyCategory.attraction, NearbyCategory.food, NearbyCategory.cafe)


@dataclass(slots=True)
class _Candidate:
    place: ResolvedPlace
    score: float
    category_key: str | None


async def build_from_spot(session: AsyncSession, payload: FromSpotRequest) -> PlanResponse:
    seed = await repositories.get_spot_brief(session, payload.contentId)
    if seed is None or seed.lat is None or seed.lng is None:
        raise PlanSpotNotFound()

    rows_by_type: dict[PlaceType, list[NearbySpotRow]] = {}
    for category in _CANDIDATE_CATEGORIES:
        rows = await find_nearby_spots(
            session,
            lat=seed.lat,
            lng=seed.lng,
            radius=CANDIDATE_RADIUS_M,
            category=category,
        )
        rows_by_type[_place_type(category)] = [
            row
            for row in rows
            if row.content_id != seed.content_id
            and row.mapy is not None
            and row.mapx is not None
            and not is_chain_branch(row.title)
        ]

    rates = await load_concentration_rates(
        session, [row.content_id for rows in rows_by_type.values() for row in rows]
    )
    popular = await _naver_popular(short_region(seed.addr1))
    pools: dict[PlaceType, list[_Candidate]] = {
        place_type: sorted(
            (_candidate(row, place_type, rates, popular) for row in rows), key=lambda c: c.score
        )
        for place_type, rows in rows_by_type.items()
    }
    pools["attraction"].insert(0, _seed_candidate(seed))

    ordered = _interleave(pools, days=payload.days)
    if len(ordered) < payload.days * MIN_SLOTS_PER_DAY:
        raise PlanNotEnoughSpots()

    response = await assemble.build_schedule(
        session,
        AssembleRequest(places=ordered, days=payload.days, sourceKind="photo", pinFirst=True),
    )
    logger.info(
        "plan.from_spot.done",
        seed=seed.content_id,
        days=payload.days,
        placed=len(ordered),
    )
    return response


def popularity_score(distance_m: float | None, rate: float | None) -> float:
    distance_km = (distance_m or 0.0) / 1000.0
    bonus = POPULARITY_MAX_KM * (rate / 100.0) if rate is not None else 0.0
    return distance_km - bonus


async def _naver_popular(region: str | None) -> list[naver.NaverPlace]:
    if not region or not naver.is_configured():
        return []
    async with httpx.AsyncClient(timeout=httpx.Timeout(5.0, connect=3.0)) as client:
        batches = await asyncio.gather(
            naver.search_local(client, f"{region} 맛집", display=NAVER_DISPLAY),
            naver.search_local(client, f"{region} 카페", display=NAVER_DISPLAY),
        )
    hits = [hit for batch in batches for hit in batch if not is_chain_branch(hit.title)]
    logger.info("plan.from_spot.naver", region=region, hits=len(hits))
    return hits


def _normalized(title: str | None) -> str:
    return "".join((title or "").split())


def _naver_endorsed(row: NearbySpotRow, popular: list[naver.NaverPlace]) -> bool:
    name = _normalized(row.title)
    if not name:
        return False
    for hit in popular:
        other = _normalized(hit.title)
        if not other or (name not in other and other not in name):
            continue
        if row.mapy is None or row.mapx is None or hit.lat is None or hit.lng is None:
            return True
        if haversine_km(row.mapy, row.mapx, hit.lat, hit.lng) <= NAVER_MATCH_MAX_KM:
            return True
    return False


def _candidate(
    row: NearbySpotRow,
    place_type: PlaceType,
    rates: dict[str, float],
    popular: list[naver.NaverPlace],
) -> _Candidate:
    score = popularity_score(row.dist, rates.get(row.content_id))
    if _naver_endorsed(row, popular):
        score -= NAVER_POPULAR_BONUS_KM
    return _Candidate(
        place=_row_place(row, place_type),
        score=score,
        category_key=row.category,
    )


def _seed_candidate(seed: repositories.SpotBrief) -> _Candidate:
    return _Candidate(place=_seed_place(seed), score=SEED_SCORE, category_key=seed.category)


def _place_type(category: NearbyCategory) -> PlaceType:
    if category is NearbyCategory.food:
        return "restaurant"
    if category is NearbyCategory.cafe:
        return "cafe"
    return "attraction"


def _interleave(pools: dict[PlaceType, list[_Candidate]], *, days: int) -> list[ResolvedPlace]:
    queues = {place_type: list(candidates) for place_type, candidates in pools.items()}
    picked: list[_Candidate] = []
    for _ in range(days):
        for place_type in _DAY_PATTERN:
            candidate = _pop(queues, place_type, picked)
            if candidate is not None:
                picked.append(candidate)
    ordered = [candidate.place for candidate in picked]
    for index, place in enumerate(ordered):
        place.extracted.orderHint = index + 1
    return ordered


def _pop(
    queues: dict[PlaceType, list[_Candidate]],
    place_type: PlaceType,
    picked: list[_Candidate],
) -> _Candidate | None:
    own = queues.get(place_type) or []
    best = _best(own, picked)
    if best is not None:
        own.remove(best)
        return best
    if place_type == "attraction":
        return None
    fallback = queues.get("attraction") or []
    best = _best(fallback, picked)
    if best is not None:
        fallback.remove(best)
    return best


def _best(queue: list[_Candidate], picked: list[_Candidate]) -> _Candidate | None:
    used_categories = {c.category_key for c in picked if c.category_key}
    best: _Candidate | None = None
    best_score = math.inf
    for candidate in queue:
        if is_near_duplicate(candidate.place.spot, _same_type_spots(picked, candidate)):
            continue
        score = candidate.score
        if candidate.category_key and candidate.category_key in used_categories:
            score += CATEGORY_REPEAT_PENALTY_KM
        if score < best_score:
            best, best_score = candidate, score
    return best


def _same_type_spots(picked: list[_Candidate], candidate: _Candidate) -> list[ResolvedSpot]:
    place_type = candidate.place.extracted.placeType
    return [
        c.place.spot
        for c in picked
        if c.place.spot is not None and c.place.extracted.placeType == place_type
    ]


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
