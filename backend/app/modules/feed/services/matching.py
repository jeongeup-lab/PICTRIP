from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.logging import get_logger
from app.modules.feed import repositories
from app.modules.feed.services.display import t1_display_url
from app.modules.feed.text import first_sentence
from app.modules.spots import services as spots_services
from app.web.errors import ResourceNotFound

logger = get_logger(__name__)

_TTL_SECONDS = 6 * 3600
_MATCH_COUNT = 3
_REVISION_KEY = "matching:revision"
_KEY = "match:{revision}:{overseas_id}"


@dataclass(frozen=True)
class MatchRow:
    content_id: str
    title: str
    region_label: str
    image_url: str
    overview_first: str | None
    cpyrht_div_cd: str | None = None


def display_image_url(row: MatchRow) -> str:
    return t1_display_url(row.image_url, row.cpyrht_div_cd) or row.image_url


async def find_matches(session: AsyncSession, redis: Redis, overseas_id: int) -> list[MatchRow]:
    revision = await _cache_revision(redis)
    cached = await _cache_get(redis, revision, overseas_id)
    overseas_validated = False
    if cached is not None:
        expected = {row.content_id: row.image_url for row in cached}
        state = await repositories.get_cached_match_state(session, overseas_id, list(expected))
        if state is None:
            await _bump_cache_revision(redis, overseas_id=overseas_id)
            raise ResourceNotFound(f"overseas spot {overseas_id} not found")
        has_embedding, current = state
        if not has_embedding:
            await _bump_cache_revision(redis, overseas_id=overseas_id)
            return []
        if current == expected:
            return cached
        revision = await _bump_cache_revision(redis, overseas_id=overseas_id)
        overseas_validated = True
    if not overseas_validated:
        brief = await repositories.get_overseas_brief(session, overseas_id)
        if brief is None:
            raise ResourceNotFound(f"overseas spot {overseas_id} not found")
        if not brief[1]:
            return []
    neighbors = await repositories.find_domestic_neighbors(
        session, overseas_id, limit=settings.MATCH_CANDIDATES
    )
    candidates = [
        (content_id, image_url)
        for content_id, image_url, distance in neighbors
        if distance <= settings.MATCH_DISTANCE_MAX
    ]
    candidate_ids = [content_id for content_id, _image_url in candidates]
    source_by_id = dict(candidates)
    rows, changed = await _hydrate(session, candidate_ids, source_by_id)
    state = await repositories.get_cached_match_state(
        session, overseas_id, [row.content_id for row in rows]
    )
    if state is None:
        await _bump_cache_revision(redis, overseas_id=overseas_id)
        raise ResourceNotFound(f"overseas spot {overseas_id} not found")
    has_embedding, current = state
    if not has_embedding:
        await _bump_cache_revision(redis, overseas_id=overseas_id)
        return []
    current_rows = [row for row in rows if current.get(row.content_id) == row.image_url]
    if changed or len(current_rows) != len(rows):
        revision = await _bump_cache_revision(redis, overseas_id=overseas_id)
    rows = current_rows[:_MATCH_COUNT]
    await _cache_set(redis, revision, overseas_id, rows)
    return rows


async def _hydrate(
    session: AsyncSession,
    candidate_ids: list[str],
    source_by_id: dict[str, str],
) -> tuple[list[MatchRow], bool]:
    if not candidate_ids:
        return [], False
    cards = await spots_services.load_active_spot_cards_by_ids(session, candidate_ids)
    region_meta = await spots_services.load_region_meta(session, candidate_ids)
    overview_map = await spots_services.load_overview_map(session, candidate_ids)
    rows: list[MatchRow] = []
    changed = False
    for cid in candidate_ids:
        card = cards.get(cid)
        if card is None or not card.first_image_url:
            changed = True
            continue
        if source_by_id.get(cid) != card.first_image_url:
            changed = True
            continue
        region_name, sigungu_name = region_meta.get(cid, (None, None))
        rows.append(
            MatchRow(
                content_id=cid,
                title=card.title,
                region_label=_region_label(region_name, sigungu_name),
                image_url=card.first_image_url,
                overview_first=first_sentence(overview_map.get(cid)),
                cpyrht_div_cd=card.cpyrht_div_cd,
            )
        )
    return rows, changed


def _region_label(region_name: str | None, sigungu_name: str | None) -> str:
    return " ".join(part for part in (region_name, sigungu_name) if part)


async def _cache_revision(redis: Redis) -> int | None:
    try:
        raw = await redis.get(_REVISION_KEY)
        return 0 if raw is None else int(raw)
    except (TypeError, ValueError) as exc:
        logger.warning("feed.match.cache_revision_corrupt", error=str(exc))
    except Exception as exc:
        logger.warning("feed.match.cache_revision_get_failed", error=str(exc))
    return None


async def _cache_get(redis: Redis, revision: int | None, overseas_id: int) -> list[MatchRow] | None:
    if revision is None:
        return None
    key = _KEY.format(revision=revision, overseas_id=overseas_id)
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


async def _cache_set(
    redis: Redis, revision: int | None, overseas_id: int, rows: list[MatchRow]
) -> None:
    if revision is None:
        return
    key = _KEY.format(revision=revision, overseas_id=overseas_id)
    payload = json.dumps([asdict(r) for r in rows])
    try:
        await redis.set(key, payload, ex=_TTL_SECONDS)
    except Exception as exc:
        logger.warning("feed.match.cache_set_failed", overseas_id=overseas_id, error=str(exc))


async def invalidate_match_cache(redis: Redis, overseas_id: int) -> None:
    await _bump_cache_revision(redis, overseas_id=overseas_id)


async def invalidate_all_match_cache(redis: Redis) -> int:
    revision = await _bump_cache_revision(redis)
    return revision or 0


async def _bump_cache_revision(redis: Redis, *, overseas_id: int | None = None) -> int | None:
    try:
        return int(await redis.incr(_REVISION_KEY))
    except Exception as exc:
        logger.warning(
            "feed.match.cache_revision_bump_failed",
            overseas_id=overseas_id,
            error=str(exc),
        )
        return None
