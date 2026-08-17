from __future__ import annotations

import re
from dataclasses import dataclass

import httpx

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_LOCAL_SEARCH_URL = "https://openapi.naver.com/v1/search/local.json"
_BLOG_SEARCH_URL = "https://openapi.naver.com/v1/search/blog.json"
_TAG_RE = re.compile(r"</?b>")


@dataclass(slots=True)
class NaverPlace:
    title: str
    category: str | None
    address: str | None
    lat: float | None
    lng: float | None


@dataclass(slots=True)
class NaverBlogPost:
    title: str
    link: str | None
    description: str | None
    postdate: str | None


def is_configured() -> bool:
    return bool(settings.NAVER_CLIENT_ID and settings.NAVER_CLIENT_SECRET)


async def search_local(
    client: httpx.AsyncClient, query: str, *, display: int = 3
) -> list[NaverPlace]:
    if not is_configured():
        return []
    try:
        resp = await client.get(
            _LOCAL_SEARCH_URL,
            params={"query": query, "display": display, "sort": "comment"},
            headers={
                "X-Naver-Client-Id": settings.NAVER_CLIENT_ID,
                "X-Naver-Client-Secret": settings.NAVER_CLIENT_SECRET,
            },
        )
        resp.raise_for_status()
        items = resp.json().get("items", [])
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("plan.naver.failed", query=query, error_type=type(exc).__name__)
        return []
    places = []
    for item in items:
        title = _TAG_RE.sub("", str(item.get("title") or "")).strip()
        if not title:
            continue
        places.append(
            NaverPlace(
                title=title,
                category=str(item.get("category") or "").strip() or None,
                address=str(item.get("roadAddress") or item.get("address") or "").strip() or None,
                lat=_coord(item.get("mapy")),
                lng=_coord(item.get("mapx")),
            )
        )
    return places


async def search_blog(
    client: httpx.AsyncClient, query: str, *, display: int = 5, sort: str | None = None
) -> list[NaverBlogPost]:
    if not is_configured():
        return []
    try:
        resp = await client.get(
            _BLOG_SEARCH_URL,
            params={"query": query, "display": display, **({"sort": sort} if sort else {})},
            headers={
                "X-Naver-Client-Id": settings.NAVER_CLIENT_ID,
                "X-Naver-Client-Secret": settings.NAVER_CLIENT_SECRET,
            },
        )
        resp.raise_for_status()
        items = resp.json().get("items", [])
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("agent.naver_blog.failed", query=query, error_type=type(exc).__name__)
        return []
    posts = []
    for item in items:
        title = _TAG_RE.sub("", str(item.get("title") or "")).strip()
        if not title:
            continue
        posts.append(
            NaverBlogPost(
                title=title,
                link=str(item.get("link") or "").strip() or None,
                description=_TAG_RE.sub("", str(item.get("description") or "")).strip() or None,
                postdate=str(item.get("postdate") or "").strip() or None,
            )
        )
    return posts


def _coord(value: object) -> float | None:
    try:
        parsed = float(str(value))
    except (TypeError, ValueError):
        return None
    if not parsed:
        return None
    return parsed / 10_000_000 if abs(parsed) > 1000 else parsed
