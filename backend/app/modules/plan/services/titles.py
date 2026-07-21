from __future__ import annotations

from collections import Counter

from app.modules.plan.schemas import ResolvedPlace

_SIDO_SUFFIXES = ("특별자치도", "특별자치시", "특별시", "광역시")
_SIGUNGU_SUFFIXES = ("시", "군")


def short_region(addr1: str | None) -> str | None:
    if not addr1:
        return None
    tokens = addr1.split()
    if not tokens:
        return None
    sido = tokens[0]
    for suffix in _SIDO_SUFFIXES:
        if sido.endswith(suffix):
            return sido.removesuffix(suffix)
    if len(tokens) > 1:
        sigungu = tokens[1]
        for suffix in _SIGUNGU_SUFFIXES:
            if sigungu.endswith(suffix) and len(sigungu) > len(suffix):
                return sigungu.removesuffix(suffix)
        return sigungu
    return sido


def plan_title(places: list[ResolvedPlace], days: int) -> str | None:
    regions = Counter(
        region
        for place in places
        if place.spot is not None and (region := short_region(place.spot.address))
    )
    if not regions:
        return None
    dominant = regions.most_common(1)[0][0]
    duration = "당일" if days == 1 else f"{days}일"
    return f"{dominant} {duration} 코스"
