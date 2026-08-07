from __future__ import annotations

import re
from dataclasses import dataclass

import httpx

from app.core.db import AsyncSession
from app.core.logging import get_logger
from app.modules.agent import naver
from app.modules.agent.naver import search_local as naver_search
from app.modules.spots.services import canonical_region_token, search_spots_by_title

logger = get_logger(__name__)

TITLE_CANDIDATES = 3
NAVER_CANDIDATES = 3
NAVER_TIMEOUT_SECONDS = 3.0
_NOISE = re.compile(r"[\s\[\]()·,.]+")


@dataclass(frozen=True, slots=True)
class Located:
    title: str
    lat: float
    lng: float
    source: str
    content_id: str | None = None


def _bare(text: str) -> str:
    return _NOISE.sub("", text)


def names_match(asked: str, found: str) -> bool:
    wanted = _bare(asked)
    if not wanted:
        return False
    haystack = _bare(found)
    if wanted in haystack:
        return True
    parts = [part for part in asked.split() if len(part) > 1]
    return len(parts) > 1 and all(_bare(part) in haystack for part in parts)


async def locate(
    session: AsyncSession,
    name: str,
    *,
    region_hint: str | None = None,
) -> Located | None:
    asked = name.strip()
    if not asked:
        return None
    terms = region_terms(region_hint)
    narrowest = terms[-1] if terms else None
    rows = await search_spots_by_title(
        session, asked, region_hint=narrowest, limit=TITLE_CANDIDATES
    )
    for row in rows:
        if row.lat is not None and row.lng is not None and names_match(asked, row.title):
            return Located(
                title=row.title,
                lat=row.lat,
                lng=row.lng,
                source="kto",
                content_id=row.content_id,
            )
    hit = await _borrow_coords_from_naver(asked, terms)
    if hit is not None:
        return hit
    logger.info("agent.geocode.miss", asked=asked, candidates=len(rows))
    return None


def region_terms(hint: str | None) -> list[str]:
    return [canonical_region_token(part) for part in (hint or "").split()]


def address_is_within(address: str | None, terms: list[str]) -> bool:
    haystack = address or ""
    return all(term in haystack for term in terms)


async def _borrow_coords_from_naver(asked: str, terms: list[str]) -> Located | None:
    if not naver.is_configured():
        return None
    query = " ".join([*terms, asked])
    try:
        async with httpx.AsyncClient(timeout=NAVER_TIMEOUT_SECONDS) as client:
            places = await naver_search(client, query, display=NAVER_CANDIDATES)
    except httpx.HTTPError as exc:
        logger.warning("agent.geocode.naver_failed", error_type=type(exc).__name__)
        return None
    for place in places:
        if place.lat is None or place.lng is None:
            continue
        if not names_match(asked, place.title):
            continue
        if not address_is_within(place.address, terms):
            continue
        return Located(title=asked, lat=place.lat, lng=place.lng, source="naver")
    return None
