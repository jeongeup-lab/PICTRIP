from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import ResourceNotFound
from app.core.logging import get_logger
from app.modules.feed import repositories
from app.modules.feed.text import first_sentence
from app.modules.spots import services as spots_services

logger = get_logger(__name__)

_TTL_SECONDS = 6 * 3600
_MATCH_COUNT = 3
_KEY = "match:{overseas_id}"


@dataclass(frozen=True)
class MatchRow:
    content_id: str
    title: str
    region_label: str
    image_url: str
    overview_first: str | None


async def find_matches(session: AsyncSession, redis: Redis, overseas_id: int) -> list[MatchRow]:
    cached = await _cache_get(redis, overseas_id)
    if cached is not None:
        return cached
    brief = await repositories.get_overseas_brief(session, overseas_id)
    if brief is None:
        raise ResourceNotFound(f"overseas spot {overseas_id} not found")
    if not brief[1]:
        return []
    neighbors = await repositories.find_domestic_neighbors(
        session, overseas_id, limit=settings.MATCH_CANDIDATES
    )
    candidate_ids = [cid for cid, dist in neighbors if dist <= settings.MATCH_DISTANCE_MAX]
    rows = await _hydrate(session, candidate_ids)
    await _cache_set(redis, overseas_id, rows)
    return rows


async def _hydrate(session: AsyncSession, candidate_ids: list[str]) -> list[MatchRow]:
    if not candidate_ids:
        return []
    cards = await spots_services.load_active_spot_cards_by_ids(session, candidate_ids)
    region_meta = await spots_services.load_region_meta(session, candidate_ids)
    overview_map = await spots_services.load_overview_map(session, candidate_ids)
    rows: list[MatchRow] = []
    for cid in candidate_ids:
        card = cards.get(cid)
        if card is None or not card.first_image_url:
            continue
        region_name, sigungu_name = region_meta.get(cid, (None, None))
        rows.append(
            MatchRow(
                content_id=cid,
                title=card.title,
                region_label=_region_label(region_name, sigungu_name),
                image_url=card.first_image_url,
                overview_first=first_sentence(overview_map.get(cid)),
            )
        )
        if len(rows) >= _MATCH_COUNT:
            break
    return rows


def _region_label(region_name: str | None, sigungu_name: str | None) -> str:
    return " ".join(part for part in (region_name, sigungu_name) if part)


async def _cache_get(redis: Redis, overseas_id: int) -> list[MatchRow] | None:
    key = _KEY.format(overseas_id=overseas_id)
    try:
        raw = await redis.get(key)
    except Exception as exc:
        logger.warning("feed.match.cache_get_failed", overseas_id=overseas_id, error=str(exc))
        return None
    if raw is None:
        return None
    try:
        return [MatchRow(**item) for item in json.loads(raw)]
    except (ValueError, TypeError) as exc:
        logger.warning("feed.match.cache_corrupt", overseas_id=overseas_id, error=str(exc))
        return None


async def _cache_set(redis: Redis, overseas_id: int, rows: list[MatchRow]) -> None:
    key = _KEY.format(overseas_id=overseas_id)
    payload = json.dumps([asdict(r) for r in rows])
    try:
        await redis.set(key, payload, ex=_TTL_SECONDS)
    except Exception as exc:
        logger.warning("feed.match.cache_set_failed", overseas_id=overseas_id, error=str(exc))
