from __future__ import annotations

import json
import re
from dataclasses import dataclass

import httpx

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_BASE_URL = "https://openapi.naver.com/v1/search/local.json"
_TIMEOUT = httpx.Timeout(5.0, connect=3.0)
_TAG_RE = re.compile(r"</?b>")
_COORD_SCALE = 10_000_000


@dataclass
class NaverPlace:
    name: str
    category: str | None
    address: str | None
    lat: float | None
    lng: float | None


def _clean(text: str) -> str:
    return _TAG_RE.sub("", text).strip()


def _coord(raw: object) -> float | None:
    try:
        value = int(str(raw))
    except (TypeError, ValueError):
        return None
    return value / _COORD_SCALE if value else None


async def search_local(query: str, *, display: int = 5) -> list[NaverPlace]:
    if not settings.NAVER_CLIENT_ID or not settings.NAVER_CLIENT_SECRET:
        logger.warning("plan.naver.no_key")
        return []

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                _BASE_URL,
                params={"query": query, "display": display, "sort": "comment"},
                headers={
                    "X-Naver-Client-Id": settings.NAVER_CLIENT_ID,
                    "X-Naver-Client-Secret": settings.NAVER_CLIENT_SECRET,
                },
            )
            resp.raise_for_status()
            payload = resp.json()
    except (httpx.HTTPError, json.JSONDecodeError, ValueError) as exc:
        logger.warning("plan.naver.request_failed", query=query, error=str(exc))
        return []

    places: list[NaverPlace] = []
    for item in payload.get("items", []):
        name = _clean(str(item.get("title", "")))
        if not name:
            continue
        places.append(
            NaverPlace(
                name=name,
                category=str(item.get("category")) or None,
                address=str(item.get("roadAddress") or item.get("address")) or None,
                lat=_coord(item.get("mapy")),
                lng=_coord(item.get("mapx")),
            )
        )
    return places
