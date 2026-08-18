from __future__ import annotations

import asyncio
from dataclasses import dataclass

import httpx

from app.core.db import AsyncSession
from app.core.logging import get_logger
from app.kto.display import t1_display_url
from app.modules.agent import kakao_places, repositories
from app.modules.agent.kakao_places import KakaoPlace, PlaceKind
from app.modules.agent.schemas import AgentSpotCard
from app.modules.agent.services.geo import haversine_km
from app.modules.agent.services.geocode import names_match_exactly
from app.modules.spots.services import NearbyCategory, category_sql
from app.naver.client import NaverBlogPost, is_configured, search_blog

logger = get_logger(__name__)

BLOG_DISPLAY = 100
BLOG_TIMEOUT_SECONDS = 1.5
MIN_DISTINCT_BLOGS = 2
MATCH_RADIUS_KM = 0.1
RESULT_LIMIT = 8


@dataclass(frozen=True, slots=True)
class Mention:
    distinct_blogs: int
    total: int


def _blogger(post: NaverBlogPost) -> str:
    link = post.link or ""
    return link.split("/")[3] if link.count("/") >= 3 else link


def count_mentions(places: list[KakaoPlace], posts: list[NaverBlogPost]) -> dict[str, Mention]:
    """카카오가 준 이름이 블로그에 나오는지 센다.

    블로그에서 상호를 추출하지 않고 대조만 한다 — 추출은 LLM 을 한 번 더 부르게 되고,
    후보마다 블로그를 치면 콜이 폭발한다.
    """
    haystacks = [(f"{p.title} {p.description or ''}", _blogger(p)) for p in posts]
    counted: dict[str, Mention] = {}
    for place in places:
        bloggers: set[str] = set()
        total = 0
        for text, blogger in haystacks:
            if place.name in text:
                total += 1
                bloggers.add(blogger)
        if total:
            counted[place.place_id] = Mention(distinct_blogs=len(bloggers), total=total)
    return counted


async def _blog_posts(query: str) -> list[NaverBlogPost]:
    if not is_configured() or not query.strip():
        return []
    timeout = httpx.Timeout(BLOG_TIMEOUT_SECONDS, connect=BLOG_TIMEOUT_SECONDS)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with asyncio.timeout(BLOG_TIMEOUT_SECONDS):
                return await search_blog(client, query, display=BLOG_DISPLAY)
    except (TimeoutError, httpx.HTTPError):
        logger.warning("agent.places.blog_timeout", query=query)
        return []


async def _kto_twin(
    session: AsyncSession, place: KakaoPlace, *, kind: PlaceKind
) -> repositories.CandidateRow | None:
    if place.lat is None or place.lng is None:
        return None
    pool = NearbyCategory.cafe if kind == "cafe" else NearbyCategory.food
    rows = await repositories.find_candidates(
        session,
        codes=None,
        region_prefixes=None,
        limit=20,
        order="id",
        pool_sql=category_sql(pool),
        title_terms=[place.name],
    )
    for row in rows:
        if row.lat is None or row.lng is None:
            continue
        if not names_match_exactly(place.name, row.title):
            continue
        if haversine_km(place.lat, place.lng, row.lat, row.lng) <= MATCH_RADIUS_KM:
            return row
    return None


def _reduced_card(place: KakaoPlace, mention: Mention | None) -> AgentSpotCard:
    return AgentSpotCard(
        contentId=place.content_id,
        source="kakao",
        title=place.name,
        regionLabel=place.address or "",
        tag=f"블로그 {mention.distinct_blogs}곳" if mention else None,
        lat=place.lat,
        lng=place.lng,
        externalUrl=place.url,
        phone=place.phone,
        distanceM=place.distance_m,
        saveable=False,
    )


def _full_card(
    row: repositories.CandidateRow, place: KakaoPlace, mention: Mention | None
) -> AgentSpotCard:
    return AgentSpotCard(
        contentId=row.content_id,
        source="kto",
        title=row.title,
        regionLabel=" ".join(p for p in (row.region_name, row.sigungu_name) if p)
        or (row.addr1 or ""),
        imageUrl=t1_display_url(row.image_url, row.cpyrht_div_cd),
        tag=f"블로그 {mention.distinct_blogs}곳" if mention else None,
        lat=row.lat,
        lng=row.lng,
        categoryGroup=row.category_group,
        hasCrowd=row.concentration_rate is not None,
        externalUrl=place.url,
        phone=place.phone,
        distanceM=place.distance_m,
        saveable=True,
    )


async def search(
    session: AsyncSession,
    *,
    kind: PlaceKind,
    region: str | None,
    landmark_coords: tuple[float, float] | None,
    dish: str | None,
    attribute: str | None,
) -> list[AgentSpotCard]:
    """KTO 가 얇은 생활권 카페·맛집을 카카오로 메운다. 저장하지 않고 매 요청 조회한다."""
    noun = "카페" if kind == "cafe" else (dish or "맛집")
    if landmark_coords is not None and dish is None:
        lat, lng = landmark_coords
        places = await kakao_places.search_nearby(kind, lat=lat, lng=lng)
    else:
        lat_lng = landmark_coords or (None, None)
        query = " ".join(part for part in (region, dish or noun) if part)
        places = await kakao_places.search_by_keyword(query, lat=lat_lng[0], lng=lat_lng[1])
    if not places:
        return []

    probe = " ".join(part for part in (region, attribute, noun) if part)
    posts = await _blog_posts(probe)
    mentions = count_mentions(places, posts)

    ranked = sorted(
        places,
        key=lambda p: (
            -(mentions[p.place_id].distinct_blogs if p.place_id in mentions else 0),
            p.distance_m if p.distance_m is not None else 10**9,
        ),
    )
    kept = [
        place
        for place in ranked
        if place.place_id not in mentions
        or mentions[place.place_id].distinct_blogs >= MIN_DISTINCT_BLOGS
    ]
    shortlist = (kept if any(p.place_id in mentions for p in kept) else ranked)[:RESULT_LIMIT]

    cards: list[AgentSpotCard] = []
    for place in shortlist:
        mention = mentions.get(place.place_id)
        twin = await _kto_twin(session, place, kind=kind)
        cards.append(
            _full_card(twin, place, mention) if twin is not None else _reduced_card(place, mention)
        )
    logger.info(
        "agent.places.done",
        kind=kind,
        candidates=len(places),
        mentioned=len(mentions),
        promoted=sum(1 for c in cards if c.source == "kto"),
    )
    return cards
