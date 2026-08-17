from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

import httpx

from app.core.db import AsyncSession
from app.core.logging import get_logger
from app.modules.agent.services.landmarks import is_landmark
from app.modules.spots.services import (
    SpotSearchRow,
    canonical_region_token,
    search_spots_by_title,
)
from app.naver import client as naver
from app.naver.client import search_local as naver_search

logger = get_logger(__name__)

TITLE_CANDIDATES = 3
NAVER_CANDIDATES = 3
NAVER_TIMEOUT_SECONDS = 3.0
_NOISE = re.compile(r"[\s\[\]()·,.]+")
_QUALIFIER = re.compile(r"[\[(][^\[\]()]*[\])]")


@dataclass(frozen=True, slots=True)
class Located:
    title: str
    lat: float
    lng: float
    source: str
    content_id: str | None = None


def _bare(text: str) -> str:
    return _NOISE.sub("", text)


def names_match_exactly(asked: str, found: str) -> bool:
    wanted = _bare(asked)
    if not wanted:
        return False
    return wanted in {_bare(found), _bare(_QUALIFIER.sub(" ", found))}


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
    usable = [row for row in rows if _is_placed(row, terms)]
    exact = _first_named(asked, usable, matcher=names_match_exactly)
    if exact is not None:
        return exact
    if is_landmark(asked):
        borrowed = await _borrow_coords_from_naver(asked, terms)
        if borrowed is not None:
            return borrowed
    loose = _first_named(asked, usable, matcher=names_match)
    if loose is not None:
        return loose
    hit = None if is_landmark(asked) else await _borrow_coords_from_naver(asked, terms)
    if hit is not None:
        return hit
    logger.info("agent.geocode.miss", asked=asked, candidates=len(rows))
    return None


def _is_placed(row: SpotSearchRow, terms: list[str]) -> bool:
    if row.lat is None or row.lng is None:
        return False
    return address_is_within(row.addr1, terms)


def _first_named(
    asked: str, rows: list[SpotSearchRow], *, matcher: Callable[[str, str], bool]
) -> Located | None:
    for row in rows:
        if row.lat is None or row.lng is None or not matcher(asked, row.title):
            continue
        return Located(
            title=row.title,
            lat=row.lat,
            lng=row.lng,
            source="kto",
            content_id=row.content_id,
        )
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
