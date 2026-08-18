from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from app.core.logging import get_logger
from app.kakao.local import kakao_local_get

logger = get_logger(__name__)

PlaceKind = Literal["cafe", "restaurant"]

_KEYWORD_PATH = "/search/keyword.json"
_CATEGORY_PATH = "/search/category.json"

CATEGORY_CODES: dict[PlaceKind, str] = {"cafe": "CE7", "restaurant": "FD6"}

PAGE_SIZE = 15
MAX_PAGES = 3
DEFAULT_RADIUS_M = 1000
MAX_RADIUS_M = 20_000


@dataclass(frozen=True, slots=True)
class KakaoPlace:
    place_id: str
    name: str
    category: str | None
    address: str | None
    phone: str | None
    url: str | None
    lat: float | None
    lng: float | None
    distance_m: int | None

    @property
    def content_id(self) -> str:
        return f"kakao:{self.place_id}"


def _coord(value: Any) -> float | None:
    try:
        parsed = float(str(value))
    except (TypeError, ValueError):
        return None
    return parsed or None


def _distance(value: Any) -> int | None:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _to_place(doc: dict[str, Any]) -> KakaoPlace | None:
    place_id = str(doc.get("id") or "").strip()
    name = str(doc.get("place_name") or "").strip()
    if not place_id or not name:
        return None
    return KakaoPlace(
        place_id=place_id,
        name=name,
        category=str(doc.get("category_name") or "").strip() or None,
        address=str(doc.get("road_address_name") or doc.get("address_name") or "").strip() or None,
        phone=str(doc.get("phone") or "").strip() or None,
        url=str(doc.get("place_url") or "").strip() or None,
        lat=_coord(doc.get("y")),
        lng=_coord(doc.get("x")),
        distance_m=_distance(doc.get("distance")),
    )


async def _collect(path: str, params: dict[str, Any], *, pages: int) -> list[KakaoPlace]:
    found: list[KakaoPlace] = []
    seen: set[str] = set()
    for page in range(1, pages + 1):
        payload = await kakao_local_get(path, params={**params, "page": page, "size": PAGE_SIZE})
        if payload is None:
            break
        docs = payload.get("documents") or []
        for doc in docs:
            place = _to_place(doc) if isinstance(doc, dict) else None
            if place is None or place.place_id in seen:
                continue
            seen.add(place.place_id)
            found.append(place)
        meta = payload.get("meta") or {}
        if not isinstance(meta, dict) or meta.get("is_end") is not False:
            break
    return found


async def search_by_keyword(
    query: str, *, lat: float | None = None, lng: float | None = None, pages: int = MAX_PAGES
) -> list[KakaoPlace]:
    """상호·요리 이름처럼 말로 지목한 것을 찾는다.

    카테고리 검색은 '횟집'을 구분하지 못해 음식점 전체를 준다 — 요리가 지정되면 이쪽이다.
    """
    cleaned = query.strip()
    if not cleaned:
        return []
    params: dict[str, Any] = {"query": cleaned}
    if lat is not None and lng is not None:
        params |= {"x": lng, "y": lat}
    return await _collect(_KEYWORD_PATH, params, pages=pages)


async def search_nearby(
    kind: PlaceKind,
    *,
    lat: float,
    lng: float,
    radius_m: int = DEFAULT_RADIUS_M,
    pages: int = MAX_PAGES,
) -> list[KakaoPlace]:
    """좌표 반경으로 업종을 훑는다. '근처' 질문은 키워드가 아니라 이쪽이다."""
    params: dict[str, Any] = {
        "category_group_code": CATEGORY_CODES[kind],
        "x": lng,
        "y": lat,
        "radius": min(max(radius_m, 1), MAX_RADIUS_M),
        "sort": "distance",
    }
    return await _collect(_CATEGORY_PATH, params, pages=pages)
