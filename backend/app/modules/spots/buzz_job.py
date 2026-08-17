from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import date, timedelta
from urllib.parse import urlsplit

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import async_session_factory
from app.core.logging import get_logger
from app.naver import client as naver

logger = get_logger(__name__)

SIDO_SHORT: dict[str, str] = {
    "서울특별시": "서울",
    "부산광역시": "부산",
    "대구광역시": "대구",
    "인천광역시": "인천",
    "광주광역시": "광주",
    "대전광역시": "대전",
    "울산광역시": "울산",
    "세종특별자치시": "세종",
    "경기도": "경기",
    "강원특별자치도": "강원",
    "충청북도": "충북",
    "충청남도": "충남",
    "전북특별자치도": "전북",
    "전라남도": "전남",
    "경상북도": "경북",
    "경상남도": "경남",
    "제주특별자치도": "제주",
}

THEMES: dict[str, str] = {
    "spot": "가볼만한 곳",
    "cafe": "감성 카페",
    "food": "맛집",
}

MIN_TITLE_LEN = 3
RECENT_DAYS = 90
DISPLAY = 100
PAUSE_SECONDS = 0.15

_CANDIDATES_SQL = """
SELECT s.content_id, s.title
FROM spots s
JOIN regions r ON r.ldong_regn_cd = s.ldong_regn_cd
WHERE s.show_flag = 1
  AND s.first_image_url IS NOT NULL
  AND s.first_image_url <> ''
  AND r.ldong_regn_nm = :region
"""

_UPSERT_SQL = """
INSERT INTO spot_buzz (content_id, scope, mentions, distinct_blogs, recent_ratio, fetched_at)
VALUES (:content_id, :scope, :mentions, :distinct_blogs, :recent_ratio, now())
ON CONFLICT (content_id, scope) DO UPDATE SET
    mentions = EXCLUDED.mentions,
    distinct_blogs = EXCLUDED.distinct_blogs,
    recent_ratio = EXCLUDED.recent_ratio,
    fetched_at = now()
"""


@dataclass
class BuzzResult:
    queries: int = 0
    posts: int = 0
    rows: int = 0
    scopes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SpotMention:
    content_id: str
    mentions: int
    distinct_blogs: int
    recent_ratio: float


def _blog_id(link: str | None) -> str:
    if not link:
        return ""
    parts = urlsplit(link)
    path = parts.path.strip("/").split("/")
    return f"{parts.netloc}/{path[0]}" if path and path[0] else parts.netloc


def aggregate_mentions(
    candidates: list[tuple[str, str]],
    posts: list[naver.NaverBlogPost],
    *,
    today: date,
) -> list[SpotMention]:
    cutoff = (today - timedelta(days=RECENT_DAYS)).strftime("%Y%m%d")
    usable = [(cid, title) for cid, title in candidates if len(title) >= MIN_TITLE_LEN]
    hits: dict[str, list[naver.NaverBlogPost]] = {}
    for post in posts:
        haystack = f"{post.title} {post.description or ''}"
        for cid, title in usable:
            if title in haystack:
                hits.setdefault(cid, []).append(post)
    out: list[SpotMention] = []
    for cid, matched in hits.items():
        blogs = {b for b in (_blog_id(p.link) for p in matched) if b}
        recent = sum(1 for p in matched if (p.postdate or "") >= cutoff)
        out.append(
            SpotMention(
                content_id=cid,
                mentions=len(matched),
                distinct_blogs=len(blogs),
                recent_ratio=recent / len(matched) if matched else 0.0,
            )
        )
    return out


async def _fetch_grid_posts(
    client: httpx.AsyncClient, query: str, *, pause: float
) -> list[naver.NaverBlogPost]:
    fresh = await naver.search_blog(client, query, display=DISPLAY, sort="date")
    await asyncio.sleep(pause)
    ranked = await naver.search_blog(client, query, display=DISPLAY, sort="sim")
    await asyncio.sleep(pause)
    seen: set[str | None] = set()
    merged: list[naver.NaverBlogPost] = []
    for post in fresh + ranked:
        if post.link in seen:
            continue
        seen.add(post.link)
        merged.append(post)
    return merged


async def _load_candidates(session: AsyncSession, region: str) -> list[tuple[str, str]]:
    result = await session.execute(text(_CANDIDATES_SQL), {"region": region})
    return [(row.content_id, row.title) for row in result]


async def run_buzz_job(
    *,
    regions: list[str] | None = None,
    themes: list[str] | None = None,
    pause: float = PAUSE_SECONDS,
    today: date | None = None,
) -> BuzzResult:
    result = BuzzResult()
    if not naver.is_configured():
        logger.warning("buzz.naver_not_configured")
        return result
    today = today or date.today()
    target_regions = {
        name: short for name, short in SIDO_SHORT.items() if regions is None or short in regions
    }
    target_themes = {k: v for k, v in THEMES.items() if themes is None or k in themes}

    async with httpx.AsyncClient(timeout=15.0) as client:
        for region_name, short in target_regions.items():
            async with async_session_factory() as session:
                candidates = await _load_candidates(session, region_name)
            if not candidates:
                continue
            for theme_key, theme_query in target_themes.items():
                posts = await _fetch_grid_posts(client, f"{short} {theme_query}", pause=pause)
                result.queries += 2
                result.posts += len(posts)
                mentions = aggregate_mentions(candidates, posts, today=today)
                if not mentions:
                    continue
                scope = f"{short}:{theme_key}"
                async with async_session_factory() as session:
                    for m in mentions:
                        await session.execute(
                            text(_UPSERT_SQL),
                            {
                                "content_id": m.content_id,
                                "scope": scope,
                                "mentions": m.mentions,
                                "distinct_blogs": m.distinct_blogs,
                                "recent_ratio": m.recent_ratio,
                            },
                        )
                    await session.commit()
                result.rows += len(mentions)
                result.scopes.append(scope)
                logger.info(
                    "buzz.scope_done",
                    scope=scope,
                    posts=len(posts),
                    matched=len(mentions),
                )
    return result
