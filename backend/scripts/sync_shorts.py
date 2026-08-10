from __future__ import annotations

import argparse
import asyncio
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import text

from app.config import settings
from app.core.db import async_session_factory
from app.core.logging import get_logger
from app.modules.agent.llm import GeminiClient
from app.modules.spots.services import find_nearby_spots

logger = get_logger(__name__)

_YT_BASE = "https://www.googleapis.com/youtube/v3"
_BROAD_QUERY = "국내여행"
_SEARCH_MAX_RESULTS = 25
_MAX_DURATION_SEC = 180
_MAX_FEED_SIZE = 60
_PER_ANCHOR_CAP = 3
_SPOTS_PER_VIDEO = 8
_SPOT_RADIUS_M = 1500
_REGION_RADIUS_M = 6000
_MIN_TITLE_LEN = 3
_GEMINI_CAP = 12
_GEMINI_SYSTEM = (
    "너는 한국 여행 쇼츠에서 장소를 찾아내는 분석기다. 영상의 화면 자막, 간판, "
    "나레이션, 풍경에서 등장하는 대한민국의 지역명(시·군 단위)과 관광지명을 "
    "찾아라. 확실히 등장하는 장소만, 등장 순서대로 담아라. 없으면 빈 배열."
)
_GEMINI_SCHEMA = {
    "type": "object",
    "properties": {"places": {"type": "array", "items": {"type": "string"}}},
    "required": ["places"],
}

_NEWS_RE = re.compile(
    r"YTN|JTBC|MBC|KBS|SBS|뉴스|News|연합|채널A|TV조선|MBN|매일경제|한국경제|OBS|YonhapNews"
)
_GENERIC_GU = {"중구", "동구", "서구", "남구", "북구"}
_DURATION_RE = re.compile(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?")

_SIGUNGU_POOL_SQL = text(
    "SELECT s.ldong_signgu_cd AS code, sg.ldong_signgu_nm AS name, "
    "AVG(s.mapy) AS cy, AVG(s.mapx) AS cx, COUNT(*) AS spot_count "
    "FROM spots s JOIN sigungus sg ON sg.ldong_signgu_cd = s.ldong_signgu_cd "
    "WHERE s.show_flag = 1 AND s.mapx IS NOT NULL AND s.mapy IS NOT NULL "
    "GROUP BY s.ldong_signgu_cd, sg.ldong_signgu_nm "
    "ORDER BY COUNT(*) DESC LIMIT 60"
)

_SIGUNGU_TITLES_SQL = text(
    "SELECT content_id, title, mapy, mapx FROM spots "
    "WHERE show_flag = 1 AND ldong_signgu_cd = :code "
    "AND mapx IS NOT NULL AND mapy IS NOT NULL "
    "AND char_length(title) >= 3 LIMIT 3000"
)


@dataclass(frozen=True)
class SigunguEntry:
    code: str
    name: str
    short_name: str
    lat: float
    lng: float


@dataclass
class ShortCandidate:
    video_id: str
    title: str
    channel_title: str
    thumbnail_url: str
    view_count: int
    duration_sec: int
    published_at: datetime
    query_sigungu: SigunguEntry | None
    description: str = ""
    tags: list[str] = field(default_factory=list)
    anchor_label: str = ""
    anchor_lat: float = 0.0
    anchor_lng: float = 0.0
    anchor_radius: int = _REGION_RADIUS_M
    spot_content_ids: list[str] = field(default_factory=list)


def short_region_name(name: str) -> str | None:
    if name in _GENERIC_GU:
        return None
    if name.endswith(("시", "군", "구")) and len(name) >= 3:
        return name[:-1]
    return name if len(name) >= 2 else None


def parse_duration_sec(raw: str) -> int:
    match = _DURATION_RE.fullmatch(raw or "")
    if not match:
        return 0
    hours, minutes, seconds = (int(g) if g else 0 for g in match.groups())
    return hours * 3600 + minutes * 60 + seconds


def title_variants(title: str) -> list[str]:
    base = title.strip()
    variants = [base]
    if "(" in base:
        variants.append(base.split("(", 1)[0].strip())
    return [v for v in variants if len(v) >= _MIN_TITLE_LEN]


async def yt_get(client: httpx.AsyncClient, path: str, **params: str | int) -> dict[str, Any]:
    params["key"] = settings.YOUTUBE_API_KEY
    for attempt in (1, 2):
        try:
            resp = await client.get(f"{_YT_BASE}/{path}", params=params)
            resp.raise_for_status()
            payload: dict[str, Any] = resp.json()
            return payload
        except httpx.HTTPError:
            if attempt == 2:
                raise
            await asyncio.sleep(2.0)
    raise RuntimeError("unreachable")


async def search_shorts(
    client: httpx.AsyncClient, query: str, published_after: str
) -> list[dict[str, Any]]:
    payload = await yt_get(
        client,
        "search",
        part="snippet",
        type="video",
        videoDuration="short",
        videoEmbeddable="true",
        regionCode="KR",
        relevanceLanguage="ko",
        order="viewCount",
        publishedAfter=published_after,
        maxResults=_SEARCH_MAX_RESULTS,
        q=query,
    )
    items: list[dict[str, Any]] = payload.get("items", [])
    return items


async def fetch_details(
    client: httpx.AsyncClient, video_ids: list[str]
) -> dict[str, dict[str, Any]]:
    details: dict[str, dict[str, Any]] = {}
    for start in range(0, len(video_ids), 50):
        payload = await yt_get(
            client,
            "videos",
            part="snippet,statistics,contentDetails",
            id=",".join(video_ids[start : start + 50]),
        )
        for item in payload.get("items", []):
            details[item["id"]] = item
    return details


def pick_rotation(pool: list[SigunguEntry], searches: int) -> list[SigunguEntry]:
    if not pool or searches <= 0:
        return []
    offset = datetime.now(UTC).timetuple().tm_yday % len(pool)
    doubled = pool + pool
    return doubled[offset : offset + min(searches, len(pool))]


def refine_anchor(
    candidate: ShortCandidate,
    sigungu: SigunguEntry,
    spot_titles: list[tuple[str, str, float, float]],
) -> None:
    haystack = " ".join([candidate.title, candidate.description, *candidate.tags])
    best: tuple[str, str, float, float] | None = None
    best_len = 0
    for content_id, title, lat, lng in spot_titles:
        for variant in title_variants(title):
            if len(variant) > best_len and variant in haystack:
                best = (content_id, title, lat, lng)
                best_len = len(variant)
    if best:
        candidate.anchor_label = best[1]
        candidate.anchor_lat = best[2]
        candidate.anchor_lng = best[3]
        candidate.anchor_radius = _SPOT_RADIUS_M
    else:
        candidate.anchor_label = sigungu.short_name
        candidate.anchor_lat = sigungu.lat
        candidate.anchor_lng = sigungu.lng
        candidate.anchor_radius = _REGION_RADIUS_M


async def load_sigungu_pool() -> list[SigunguEntry]:
    async with async_session_factory() as session:
        rows = (await session.execute(_SIGUNGU_POOL_SQL)).all()
    pool = []
    for row in rows:
        short = short_region_name(row.name)
        if short:
            pool.append(
                SigunguEntry(
                    code=row.code,
                    name=row.name,
                    short_name=short,
                    lat=float(row.cy),
                    lng=float(row.cx),
                )
            )
    return pool


async def load_sigungu_titles(code: str) -> list[tuple[str, str, float, float]]:
    async with async_session_factory() as session:
        rows = (await session.execute(_SIGUNGU_TITLES_SQL, {"code": code})).all()
    return [(r.content_id, r.title, float(r.mapy), float(r.mapx)) for r in rows]


async def match_spots(candidate: ShortCandidate) -> list[str]:
    async with async_session_factory() as session:
        rows = await find_nearby_spots(
            session,
            lat=candidate.anchor_lat,
            lng=candidate.anchor_lng,
            radius=candidate.anchor_radius,
            category=None,
        )
    with_image = [r.content_id for r in rows if r.first_image_url]
    without_image = [r.content_id for r in rows if not r.first_image_url]
    return (with_image + without_image)[:_SPOTS_PER_VIDEO]


def build_candidates(
    search_hits: dict[str, SigunguEntry | None], details: dict[str, dict[str, Any]]
) -> list[ShortCandidate]:
    candidates = []
    for video_id, sigungu in search_hits.items():
        item = details.get(video_id)
        if not item:
            continue
        snippet = item.get("snippet", {})
        duration_sec = parse_duration_sec(item.get("contentDetails", {}).get("duration", ""))
        if duration_sec == 0 or duration_sec > _MAX_DURATION_SEC:
            continue
        title = snippet.get("title", "")
        channel = snippet.get("channelTitle", "")
        if _NEWS_RE.search(channel) or _NEWS_RE.search(title):
            continue
        thumbs = snippet.get("thumbnails", {})
        thumb = (thumbs.get("high") or thumbs.get("medium") or thumbs.get("default") or {}).get(
            "url"
        )
        published_raw = snippet.get("publishedAt")
        if not (title and channel and thumb and published_raw):
            continue
        candidates.append(
            ShortCandidate(
                video_id=video_id,
                title=title,
                channel_title=channel,
                thumbnail_url=thumb,
                view_count=int(item.get("statistics", {}).get("viewCount", 0)),
                duration_sec=duration_sec,
                published_at=datetime.fromisoformat(published_raw.replace("Z", "+00:00")),
                query_sigungu=sigungu,
                description=snippet.get("description", ""),
                tags=list(snippet.get("tags", [])),
            )
        )
    return candidates


def merge_places_text(candidate: ShortCandidate, places: list[str]) -> None:
    extra = " ".join(p.strip() for p in places if p and p.strip())
    if extra:
        candidate.description = f"{candidate.description} {extra}".strip()


async def gemini_places(client: GeminiClient, video_id: str) -> list[str]:
    payload = await client.generate_json(
        system=_GEMINI_SYSTEM,
        user_text="이 영상에 등장하는 장소를 알려줘.",
        video_uri=f"https://www.youtube.com/watch?v={video_id}",
        response_schema=_GEMINI_SCHEMA,
    )
    places = payload.get("places", []) if isinstance(payload, dict) else []
    return [p for p in places if isinstance(p, str)]


def resolve_broad_sigungu(
    candidate: ShortCandidate, pool: list[SigunguEntry]
) -> SigunguEntry | None:
    haystack = " ".join([candidate.title, candidate.description, *candidate.tags])
    best: SigunguEntry | None = None
    best_len = 0
    for entry in pool:
        if len(entry.short_name) > best_len and entry.short_name in haystack:
            best = entry
            best_len = len(entry.short_name)
    return best


def rank_feed(candidates: list[ShortCandidate]) -> list[ShortCandidate]:
    ranked = []
    per_anchor: dict[str, int] = {}
    for candidate in sorted(candidates, key=lambda c: -c.view_count):
        used = per_anchor.get(candidate.anchor_label, 0)
        if used >= _PER_ANCHOR_CAP:
            continue
        per_anchor[candidate.anchor_label] = used + 1
        ranked.append(candidate)
        if len(ranked) >= _MAX_FEED_SIZE:
            break
    return ranked


async def write_feed(feed: list[ShortCandidate]) -> None:
    async with async_session_factory() as session:
        await session.execute(text("DELETE FROM travel_shorts"))
        for rank, candidate in enumerate(feed, start=1):
            await session.execute(
                text(
                    "INSERT INTO travel_shorts (video_id, title, channel_title, "
                    "thumbnail_url, view_count, duration_sec, published_at, "
                    "anchor_label, rank) VALUES (:video_id, :title, :channel_title, "
                    ":thumbnail_url, :view_count, :duration_sec, :published_at, "
                    ":anchor_label, :rank)"
                ),
                {
                    "video_id": candidate.video_id,
                    "title": candidate.title,
                    "channel_title": candidate.channel_title,
                    "thumbnail_url": candidate.thumbnail_url,
                    "view_count": candidate.view_count,
                    "duration_sec": candidate.duration_sec,
                    "published_at": candidate.published_at,
                    "anchor_label": candidate.anchor_label[:80],
                    "rank": rank,
                },
            )
            for spot_rank, content_id in enumerate(candidate.spot_content_ids, start=1):
                await session.execute(
                    text(
                        "INSERT INTO travel_shorts_spots (video_id, content_id, rank) "
                        "VALUES (:video_id, :content_id, :rank)"
                    ),
                    {
                        "video_id": candidate.video_id,
                        "content_id": content_id,
                        "rank": spot_rank,
                    },
                )
        await session.commit()


async def main() -> None:
    parser = argparse.ArgumentParser(description="Load trending travel shorts into travel_shorts.")
    parser.add_argument("--searches", type=int, default=20, help="regional search queries per run")
    parser.add_argument("--days", type=int, default=14, help="publishedAfter window")
    parser.add_argument("--dry-run", action="store_true", help="fetch + match, no DB writes")
    args = parser.parse_args()

    if not settings.YOUTUBE_API_KEY:
        raise SystemExit("YOUTUBE_API_KEY is not configured")

    pool = await load_sigungu_pool()
    rotation = pick_rotation(pool, args.searches)
    published_after = (datetime.now(UTC) - timedelta(days=args.days)).strftime("%Y-%m-%dT%H:%M:%SZ")

    search_hits: dict[str, SigunguEntry | None] = {}
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
        for entry in rotation:
            for item in await search_shorts(client, f"{entry.short_name} 여행", published_after):
                search_hits.setdefault(item["id"]["videoId"], entry)
        for item in await search_shorts(client, _BROAD_QUERY, published_after):
            search_hits.setdefault(item["id"]["videoId"], None)
        details = await fetch_details(client, list(search_hits))

    candidates = build_candidates(search_hits, details)
    totals = {
        "searched": len(search_hits),
        "candidates": len(candidates),
        "no_place": 0,
        "gemini_tried": 0,
        "gemini_resolved": 0,
        "ranked": 0,
        "matched": 0,
    }

    titles_cache: dict[str, list[tuple[str, str, float, float]]] = {}

    async def resolve_candidate(candidate: ShortCandidate) -> bool:
        sigungu = candidate.query_sigungu or resolve_broad_sigungu(candidate, pool)
        if sigungu is None:
            return False
        if sigungu.code not in titles_cache:
            titles_cache[sigungu.code] = await load_sigungu_titles(sigungu.code)
        refine_anchor(candidate, sigungu, titles_cache[sigungu.code])
        return True

    resolved = []
    unresolved = []
    for candidate in candidates:
        if await resolve_candidate(candidate):
            resolved.append(candidate)
        else:
            unresolved.append(candidate)

    if unresolved and settings.GEMINI_API_KEY:
        unresolved.sort(key=lambda c: -c.view_count)
        gemini = GeminiClient()
        try:
            for candidate in unresolved[:_GEMINI_CAP]:
                totals["gemini_tried"] += 1
                try:
                    places = await gemini_places(gemini, candidate.video_id)
                except Exception as exc:
                    logger.warning(
                        "shorts.gemini.failed",
                        video=candidate.video_id,
                        error_type=type(exc).__name__,
                    )
                    continue
                merge_places_text(candidate, places)
                if await resolve_candidate(candidate):
                    totals["gemini_resolved"] += 1
                    resolved.append(candidate)
        finally:
            await gemini.aclose()
    totals["no_place"] = len(candidates) - len(resolved)

    feed = rank_feed(resolved)
    totals["ranked"] = len(feed)
    for candidate in feed:
        candidate.spot_content_ids = await match_spots(candidate)
        if candidate.spot_content_ids:
            totals["matched"] += 1
    feed = [c for c in feed if c.spot_content_ids]

    if args.dry_run:
        for candidate in feed[:10]:
            logger.info(
                "shorts.dry_run",
                video=candidate.video_id,
                anchor=candidate.anchor_label,
                views=candidate.view_count,
                spots=len(candidate.spot_content_ids),
            )
    else:
        await write_feed(feed)
    logger.info("shorts.sync.done", **totals)


if __name__ == "__main__":
    asyncio.run(main())
