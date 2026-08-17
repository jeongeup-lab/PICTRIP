from __future__ import annotations

import json
import math
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import date

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.kto.display import t1_display_url
from app.modules.feed import repositories as repo
from app.modules.spots import services as spots_services

logger = get_logger(__name__)

CARD_COUNT = 10
TASTE_PICK_COUNT = 12
MIN_TASTE_SEEDS = 3

_NEARBY_RADIUS_M = 5000
_NEARBY_TTL = 600
_EMPTY_TTL = 120
_TRENDING_TTL = 3600
_TASTE_PICKS_TTL = 21_600
_SEED_LIMIT = 30
_NEIGHBOR_OVERFETCH = 3
_CACHE_VERSION = "v2"


@dataclass(frozen=True)
class HomeCardRow:
    content_id: str
    title: str
    region_label: str
    image_url: str | None
    rank: int | None = None
    dist: float | None = None
    category: str | None = None
    tag: str | None = None
    anchor_title: str | None = None


@dataclass(frozen=True)
class HomeRanking:
    cards: list[HomeCardRow]
    base_date: str | None


@dataclass(frozen=True)
class RecommendationRow:
    ready: bool
    saved_count: int
    min_saved: int
    items: list[HomeCardRow]


async def load_nearby_ranked(
    session: AsyncSession, redis: Redis, *, lat: float, lng: float, limit: int = CARD_COUNT
) -> HomeRanking:
    key = f"home:nearby:{_CACHE_VERSION}:{lat:.3f}:{lng:.3f}:{limit}"
    cached = await _cache_get(redis, key)
    if cached is not None:
        return cached

    dlat = _NEARBY_RADIUS_M / 111_320.0
    dlng = _NEARBY_RADIUS_M / (111_320.0 * max(math.cos(math.radians(lat)), 0.01))
    rows = await repo.fetch_nearby_ranked(
        session,
        lat=lat,
        lng=lng,
        min_lat=lat - dlat,
        max_lat=lat + dlat,
        min_lng=lng - dlng,
        max_lng=lng + dlng,
        radius=_NEARBY_RADIUS_M,
        limit=limit,
    )
    ranking = HomeRanking(
        cards=[_card(row, rank=idx) for idx, row in enumerate(rows, start=1)],
        base_date=_shared_base_date(row.base_ymd for row in rows),
    )
    await _cache_set(redis, key, ranking, _NEARBY_TTL if ranking.cards else _EMPTY_TTL)
    return ranking


async def load_trending(
    session: AsyncSession, redis: Redis, *, limit: int = CARD_COUNT
) -> HomeRanking:
    key = f"home:trending:{_CACHE_VERSION}:{limit}"
    cached = await _cache_get(redis, key)
    if cached is not None:
        return cached

    rows = await spots_services.load_hot_spots(session, limit=limit)
    usable = [row for row in rows if row.content_id]
    ranking = HomeRanking(
        cards=[
            HomeCardRow(
                content_id=row.content_id,
                title=row.title,
                region_label=row.region_label,
                image_url=t1_display_url(row.first_image_url, row.cpyrht_div_cd),
                rank=idx,
                tag=_last_token(row.region_label),
            )
            for idx, row in enumerate(usable, start=1)
        ],
        base_date=_shared_base_date(row.base_ymd for row in usable),
    )
    await _cache_set(redis, key, ranking, _TRENDING_TTL if ranking.cards else _EMPTY_TTL)
    return ranking


async def load_taste_picks(
    session: AsyncSession,
    redis: Redis,
    *,
    limit: int = TASTE_PICK_COUNT,
    category: str | None = None,
) -> list[HomeCardRow]:
    key = f"home:taste-picks:{_CACHE_VERSION}:{category or 'all'}:{limit}"
    cached = await _cache_get(redis, key)
    if cached is not None:
        return cached.cards

    rows = await repo.fetch_taste_picks(session, limit=limit, category=category)
    ranking = HomeRanking(cards=[_card(row) for row in rows], base_date=None)
    await _cache_set(redis, key, ranking, _TASTE_PICKS_TTL if ranking.cards else _EMPTY_TTL)
    return ranking.cards


async def load_recommendations(
    session: AsyncSession,
    *,
    user_id: int,
    lat: float | None,
    lng: float | None,
    limit: int = CARD_COUNT,
) -> RecommendationRow:
    saved, _, _ = await spots_services.list_saved_spots(session, user_id=user_id, limit=_SEED_LIMIT)
    if len(saved) < MIN_TASTE_SEEDS:
        return RecommendationRow(
            ready=False, saved_count=len(saved), min_saved=MIN_TASTE_SEEDS, items=[]
        )

    title_by_id = {card.content_id: card.title for card in saved}
    rows = await repo.fetch_taste_neighbors(
        session,
        seed_ids=list(title_by_id),
        lat=lat,
        lng=lng,
        limit=limit * _NEIGHBOR_OVERFETCH,
    )
    items = [
        _card(row, anchor_title=title_by_id.get(row.anchor_content_id or ""))
        for row in _diversified(rows, limit)
    ]
    return RecommendationRow(
        ready=bool(items), saved_count=len(saved), min_saved=MIN_TASTE_SEEDS, items=items
    )


def _diversified(rows: list[repo.HomeSpotRow], limit: int) -> list[repo.HomeSpotRow]:
    picked: list[repo.HomeSpotRow] = []
    seen_anchors: set[str] = set()
    deferred: list[repo.HomeSpotRow] = []
    for row in rows:
        anchor = row.anchor_content_id or ""
        if anchor in seen_anchors:
            deferred.append(row)
            continue
        seen_anchors.add(anchor)
        picked.append(row)
        if len(picked) == limit:
            return picked
    return (picked + deferred)[:limit]


def _card(
    row: repo.HomeSpotRow, *, rank: int | None = None, anchor_title: str | None = None
) -> HomeCardRow:
    region_label = " ".join(p for p in (row.region_name, row.sigungu_name) if p)
    return HomeCardRow(
        content_id=row.content_id,
        title=row.title,
        region_label=region_label,
        image_url=t1_display_url(row.first_image_url, row.cpyrht_div_cd),
        rank=rank,
        dist=row.dist,
        category=row.category,
        tag=row.category or _last_token(region_label) or None,
        anchor_title=anchor_title,
    )


def _last_token(label: str) -> str | None:
    parts = label.split()
    return parts[-1] if parts else None


def _shared_base_date(dates: Iterable[date | None]) -> str | None:
    seen = {d for d in dates if d is not None}
    return seen.pop().isoformat() if len(seen) == 1 else None


async def _cache_get(redis: Redis, key: str) -> HomeRanking | None:
    try:
        raw = await redis.get(key)
    except Exception as exc:
        logger.warning("feed.home.cache_get_failed", key=key, error=str(exc))
        return None
    if not raw:
        return None
    try:
        payload = json.loads(raw)
        return HomeRanking(
            cards=[HomeCardRow(**item) for item in payload["cards"]],
            base_date=payload["baseDate"],
        )
    except (ValueError, TypeError, KeyError) as exc:
        logger.warning("feed.home.cache_corrupt", key=key, error=str(exc))
        return None


async def _cache_set(redis: Redis, key: str, ranking: HomeRanking, ttl: int) -> None:
    payload = {
        "baseDate": ranking.base_date,
        "cards": [asdict(c) for c in ranking.cards],
    }
    try:
        await redis.set(key, json.dumps(payload, ensure_ascii=False), ex=ttl)
    except Exception as exc:
        logger.warning("feed.home.cache_set_failed", key=key, error=str(exc))
