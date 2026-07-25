from __future__ import annotations

import asyncio
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.config import settings
from app.core.db import AsyncSession
from app.core.logging import get_logger
from app.kto.client import KtoClient, KtoService
from app.kto.display import t1_display_url
from app.modules.agent import naver
from app.modules.agent.schemas import (
    ExtractedPlace,
    ResolvedPlace,
    ResolvedSpot,
    ResolveStatus,
)
from app.modules.agent.services.geo import haversine_km
from app.modules.spots.services import (
    SpotSearchRow,
    map_region_tokens_to_sido,
    search_spots_by_title,
)
from app.web.errors import KtoApiUnavailable

logger = get_logger(__name__)

MATCH_CONFIDENCE = 0.6
AMBIGUOUS_CONFIDENCE = 0.45
PROMOTED_CONFIDENCE = 0.9
NAVER_ONLY_CONFIDENCE = 0.7
KTO_MATCH_CONFIDENCE = 0.65
NAVER_PROMOTE_MAX_KM = 0.7
NAVER_CONCURRENCY = 5

COMMERCIAL_TYPES = {"restaurant", "cafe", "hotel"}
PLACE_CONTENT_TYPES: dict[str, list[int]] = {
    "attraction": [12, 14, 25, 28],
    "restaurant": [39],
    "cafe": [39],
    "hotel": [32],
}

_STATUS_RANK = {"matched": 3, "naver_only": 2, "ambiguous": 1, "unmatched": 0}


@dataclass(slots=True)
class RegionContext:
    token_sido: dict[str, str] = field(default_factory=dict)
    allowed: set[str] = field(default_factory=set)

    def place_sido(self, place: ExtractedPlace) -> str | None:
        for token in _hint_tokens(place.regionHint):
            sido = self.token_sido.get(token)
            if sido:
                return sido
        return None

    def allowed_for(self, place: ExtractedPlace) -> set[str]:
        own = self.place_sido(place)
        return {own} if own else self.allowed


async def resolve_places(
    session: AsyncSession,
    kto: KtoClient | None,
    places: list[ExtractedPlace],
) -> list[ResolvedPlace]:
    ctx = await _build_region_context(session, places)
    results: list[ResolvedPlace | None] = [None] * len(places)
    naver_indexes: list[int] = []

    for index, place in enumerate(places):
        if place.placeType == "region":
            results[index] = ResolvedPlace(extracted=place)
            continue
        if place.placeType in COMMERCIAL_TYPES:
            naver_indexes.append(index)
            continue
        candidate = await _kto_local(session, place, ctx)
        if candidate and candidate.status == "matched":
            results[index] = candidate
        else:
            results[index] = candidate
            naver_indexes.append(index)

    naver_hits = await _naver_batch(ctx, [places[i] for i in naver_indexes])

    for position, index in enumerate(naver_indexes):
        place = places[index]
        derived = await _from_naver(session, place, ctx, naver_hits[position])
        if derived is None and results[index] is None and place.placeType in COMMERCIAL_TYPES:
            results[index] = await _kto_local(session, place, ctx)
        results[index] = _pick(results[index], derived)

    for index, place in enumerate(places):
        current = results[index]
        if current is None or current.status == "unmatched":
            fallback = await _kto_api_fallback(kto, place, ctx)
            results[index] = _pick(current, fallback)

    resolved = [
        r if r is not None else ResolvedPlace(extracted=places[i]) for i, r in enumerate(results)
    ]
    logger.info(
        "plan.resolve.done",
        total=len(resolved),
        allowed_regions=sorted(ctx.allowed),
        **{s: sum(1 for r in resolved if r.status == s) for s in _STATUS_RANK},
    )
    return resolved


def _pick(current: ResolvedPlace | None, candidate: ResolvedPlace | None) -> ResolvedPlace | None:
    if candidate is None:
        return current
    if current is None:
        return candidate
    current_key = (_STATUS_RANK[current.status], current.confidence)
    candidate_key = (_STATUS_RANK[candidate.status], candidate.confidence)
    return candidate if candidate_key > current_key else current


def _hint_tokens(region_hint: str | None) -> list[str]:
    if not region_hint:
        return []
    cleaned = region_hint.strip()
    tokens = cleaned.split()
    return [cleaned, *tokens] if len(tokens) > 1 else tokens


async def _build_region_context(
    session: AsyncSession, places: list[ExtractedPlace]
) -> RegionContext:
    tokens = {token for place in places for token in _hint_tokens(place.regionHint)}
    token_sido = await map_region_tokens_to_sido(session, tokens)
    ctx = RegionContext(token_sido=token_sido)
    votes = Counter(sido for place in places if (sido := ctx.place_sido(place)))
    ctx.allowed = set(votes)
    return ctx


def _sido_ok(address: str | None, allowed: set[str]) -> bool:
    if not allowed:
        return True
    if not address:
        return False
    return any(address.startswith(sido) for sido in allowed)


def _queries(place: ExtractedPlace) -> list[str]:
    queries: list[str] = []
    for name in (place.nameKo, place.name):
        cleaned = (name or "").strip()
        if cleaned and cleaned not in queries:
            queries.append(cleaned)
    for query in list(queries):
        stripped = _strip_region_prefix(query, place.regionHint)
        if stripped and stripped not in queries:
            queries.append(stripped)
    return queries


def _strip_region_prefix(query: str, region_hint: str | None) -> str | None:
    if not region_hint:
        return None
    for token in (region_hint.strip(), *region_hint.strip().split()):
        if token and query.startswith(token):
            remainder = query[len(token) :].strip()
            if len(remainder) >= 3:
                return remainder
    return None


async def _kto_local(
    session: AsyncSession, place: ExtractedPlace, ctx: RegionContext
) -> ResolvedPlace | None:
    allowed = ctx.allowed_for(place)
    preferred = PLACE_CONTENT_TYPES.get(place.placeType)
    region_filters: list[str | None] = []
    hint_token = _region_token(place.regionHint)
    if hint_token:
        region_filters.append(hint_token)
    region_filters.extend(sido for sido in sorted(allowed) if sido != hint_token)
    if not region_filters:
        region_filters.append(None)

    best: SpotSearchRow | None = None
    for query in _queries(place):
        for region in region_filters:
            rows = await search_spots_by_title(
                session, query, region_hint=region, preferred_content_types=preferred
            )
            for row in rows:
                if not _sido_ok(row.addr1, allowed):
                    continue
                if row.similarity >= MATCH_CONFIDENCE:
                    return _kto_result(place, row, "matched")
                if best is None or row.similarity > best.similarity:
                    best = row
            if rows:
                break
    if best and best.similarity >= AMBIGUOUS_CONFIDENCE:
        return _kto_result(place, best, "ambiguous")
    return None


def _region_token(region_hint: str | None) -> str | None:
    if not region_hint:
        return None
    tokens = region_hint.strip().split()
    return tokens[-1] if tokens else None


def _kto_result(place: ExtractedPlace, row: SpotSearchRow, status: ResolveStatus) -> ResolvedPlace:
    return ResolvedPlace(
        extracted=place,
        spot=ResolvedSpot(
            source="kto",
            contentId=row.content_id,
            title=row.title,
            category=row.category,
            address=row.addr1,
            lat=row.lat,
            lng=row.lng,
            imageUrl=t1_display_url(row.image_url, row.cpyrht_div_cd),
        ),
        confidence=round(row.similarity, 3),
        status=status,
    )


async def _naver_batch(
    ctx: RegionContext, places: list[ExtractedPlace]
) -> list[list[naver.NaverPlace]]:
    if not places or not naver.is_configured():
        return [[] for _ in places]
    semaphore = asyncio.Semaphore(NAVER_CONCURRENCY)
    async with httpx.AsyncClient(timeout=httpx.Timeout(5.0, connect=3.0)) as client:

        async def one(place: ExtractedPlace) -> list[naver.NaverPlace]:
            async with semaphore:
                return await naver.search_local(client, _naver_query(place, ctx))

        return list(await asyncio.gather(*(one(p) for p in places)))


def _naver_query(place: ExtractedPlace, ctx: RegionContext) -> str:
    name = (place.nameKo or place.name).strip()
    region = _region_token(place.regionHint)
    if not region:
        sidos = ctx.allowed_for(place)
        region = sorted(sidos)[0] if len(sidos) == 1 else None
    return f"{region} {name}" if region and not name.startswith(region) else name


async def _from_naver(
    session: AsyncSession,
    place: ExtractedPlace,
    ctx: RegionContext,
    hits: list[naver.NaverPlace],
) -> ResolvedPlace | None:
    allowed = ctx.allowed_for(place)
    hit = next((h for h in hits if _sido_ok(h.address, allowed)), None)
    if hit is None:
        return None
    promoted = await _promote_to_kto(session, place, hit)
    if promoted:
        return promoted
    return ResolvedPlace(
        extracted=place,
        spot=ResolvedSpot(
            source="naver",
            contentId=None,
            title=hit.title,
            category=_naver_category(hit.category),
            address=hit.address,
            lat=hit.lat,
            lng=hit.lng,
            imageUrl=None,
        ),
        confidence=NAVER_ONLY_CONFIDENCE,
        status="naver_only",
    )


def _naver_category(category: str | None) -> str | None:
    if not category:
        return None
    return category.split(">")[-1].strip() or None


async def _promote_to_kto(
    session: AsyncSession, place: ExtractedPlace, hit: naver.NaverPlace
) -> ResolvedPlace | None:
    region = _address_region_token(hit.address)
    preferred = PLACE_CONTENT_TYPES.get(place.placeType)
    for query in _promotion_queries(place, hit):
        rows = await search_spots_by_title(
            session, query, region_hint=region, preferred_content_types=preferred
        )
        for row in rows:
            if _close_enough(row, hit):
                promoted = _kto_result(place, row, "matched")
                promoted.confidence = PROMOTED_CONFIDENCE
                return promoted
    return None


def _promotion_queries(place: ExtractedPlace, hit: naver.NaverPlace) -> list[str]:
    queries = [hit.title]
    tokens = hit.title.split()
    if len(tokens) > 1 and tokens[-1].endswith("점"):
        queries.append(" ".join(tokens[:-1]))
    base = (place.nameKo or place.name).strip()
    if base and base not in queries:
        queries.append(base)
    return queries


def _address_region_token(address: str | None) -> str | None:
    if not address:
        return None
    tokens = address.split()
    return tokens[1] if len(tokens) > 1 else tokens[0]


def _close_enough(row: SpotSearchRow, hit: naver.NaverPlace) -> bool:
    if None in (row.lat, row.lng, hit.lat, hit.lng):
        return False
    return haversine_km(row.lat, row.lng, hit.lat, hit.lng) <= NAVER_PROMOTE_MAX_KM  # type: ignore[arg-type]


async def _kto_api_fallback(
    kto: KtoClient | None, place: ExtractedPlace, ctx: RegionContext
) -> ResolvedPlace | None:
    if kto is None or not settings.KTO_SERVICE_KEY:
        return None
    query = (place.nameKo or place.name).strip()
    if not query:
        return None
    try:
        items = await kto.call(KtoService.KOR, "searchKeyword2", keyword=query, numOfRows=5)
    except KtoApiUnavailable:
        return None
    allowed = ctx.allowed_for(place)
    for item in items:
        spot = _kto_item_to_spot(item)
        if spot is None or not _sido_ok(spot.address, allowed):
            continue
        if query in spot.title or spot.title in query:
            return ResolvedPlace(
                extracted=place,
                spot=spot,
                confidence=KTO_MATCH_CONFIDENCE,
                status="matched",
            )
    return None


def _kto_item_to_spot(item: dict[str, Any]) -> ResolvedSpot | None:
    content_id = str(item.get("contentid") or "").strip()
    title = str(item.get("title") or "").strip()
    if not content_id or not title:
        return None
    return ResolvedSpot(
        source="kto",
        contentId=content_id,
        title=title,
        address=str(item.get("addr1") or "").strip() or None,
        lat=_to_float(item.get("mapy")),
        lng=_to_float(item.get("mapx")),
        imageUrl=t1_display_url(
            str(item.get("firstimage") or "").strip() or None,
            str(item.get("cpyrhtDivCd") or "").strip() or None,
        ),
    )


def _to_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed else None
