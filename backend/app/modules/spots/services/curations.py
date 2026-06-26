"""Curation resolution — handpicked spots, else the quality-gate random pool (S07 §3.3).

Resolved content_ids are cached daily; cache TTL adds a stable per-curation jitter
to avoid the whole feed expiring at once (thundering herd). Determinism uses hashlib,
not the salted builtin hash(), so picks are stable across processes.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from redis.asyncio import Redis
from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ResourceNotFound
from app.core.time import kst_now, seconds_until_kst_midnight
from app.modules.images.services import spot_has_embedding_clause
from app.modules.spots.models import Curation, CurationSpot, Spot, SpotDetail, SpotMood
from app.modules.spots.services.cards import (
    cover_url,
    load_congestion,
    load_spot_cards_by_ids,
)
from app.modules.spots.services.rows import SpotCardRow

# Size of the candidate pool before the deterministic pick, and how many to show.
_POOL_LIMIT = 30
_SHOW = 8
_JITTER_MAX = 601  # 0..600 inclusive


@dataclass
class CurationRow:
    """Curation projection for the feed (no ORM leakage to routes)."""

    id: int
    type: str
    slug: str
    title: str
    subtitle: str | None
    region_cd: str | None
    mood_id: int | None
    cover_spot_id: str | None
    position: int
    lead: str | None = None
    intro: str | None = None


@dataclass
class CurationDetailRow:
    """Curation detail projection (S09 §5.2) — header fields + resolved spots.

    subtitle is intentionally absent: the detail screen omits it.
    """

    id: int
    type: str
    slug: str
    title: str
    lead: str | None
    intro: str | None
    cover_url: str | None
    spots: list[SpotCardRow]


def _jitter(curation_id: int) -> int:
    """Stable per-curation cache jitter in 0..600s (NOT random)."""
    return curation_id % _JITTER_MAX


def _seed_pick(curation_id: int, ordered_ids: list[str]) -> list[str]:
    """Deterministically pick/rotate up to _SHOW ids.

    Same curation_id + KST date yields the same selection (sha256 rotation offset):
    the daily feed shifts but is reproducible across processes.
    """
    if not ordered_ids:
        return []
    date_str = kst_now().strftime("%Y-%m-%d")
    digest = hashlib.sha256(f"{curation_id}|{date_str}".encode()).hexdigest()
    offset = int(digest, 16) % len(ordered_ids)
    rotated = ordered_ids[offset:] + ordered_ids[:offset]
    return rotated[:_SHOW]


async def load_curation(session: AsyncSession, curation_id: int) -> CurationRow:
    row = (await session.execute(select(Curation).where(Curation.id == curation_id))).scalar_one()
    return _to_row(row)


def _to_row(row: Curation) -> CurationRow:
    return CurationRow(
        id=row.id,
        type=row.type,
        slug=row.slug,
        title=row.title,
        subtitle=row.subtitle,
        region_cd=row.region_cd,
        mood_id=row.mood_id,
        cover_spot_id=row.cover_spot_id,
        position=row.position,
        lead=row.lead,
        intro=row.intro,
    )


async def list_published_curations(session: AsyncSession, type_: str) -> list[CurationRow]:
    """Published curations of one ``type``, ordered by ``position`` (feed order)."""
    rows = (
        await session.execute(
            select(Curation)
            .where(Curation.type == type_, Curation.is_published.is_(True))
            .order_by(Curation.position)
        )
    ).scalars()
    return [_to_row(r) for r in rows]


async def _handpicked_ids(session: AsyncSession, curation_id: int) -> list[str]:
    rows = (
        await session.execute(
            select(CurationSpot.content_id)
            .where(CurationSpot.curation_id == curation_id)
            .order_by(CurationSpot.position)
        )
    ).scalars()
    return list(rows)


async def _pool_ids(session: AsyncSession, curation: CurationRow) -> list[str]:
    """Quality-gate random pool candidate ids (top ~30, ranked by quality).

    Ranking uses EXISTS subqueries — never a JOIN/CTE against the HNSW index.
    """
    has_overview = exists().where(SpotDetail.content_id == Spot.content_id)
    has_embedding = spot_has_embedding_clause(Spot.content_id)

    stmt = select(Spot.content_id).where(
        Spot.show_flag == 1,
        Spot.first_image_url.isnot(None),
    )
    if curation.type == "region":
        stmt = stmt.where(Spot.ldong_regn_cd == curation.region_cd)
    elif curation.type == "mood":
        in_mood = exists().where(
            SpotMood.content_id == Spot.content_id,
            SpotMood.mood_id == curation.mood_id,
        )
        stmt = stmt.where(in_mood)

    # Rank: overview present DESC, embedding present DESC, then content_id for a
    # stable tiebreak (deterministic candidate ordering before the daily pick).
    stmt = stmt.order_by(
        has_overview.desc(),
        has_embedding.desc(),
        Spot.content_id,
    ).limit(_POOL_LIMIT)

    rows = (await session.execute(stmt)).scalars()
    return list(rows)


async def resolve_curation_ids(
    session: AsyncSession,
    redis: Redis,
    curation: CurationRow,
) -> list[str]:
    """Resolve a curation's display content_ids (handpicked, else quality-gate pool).

    Returns up to _SHOW ordered ids. Cached daily. Hydration is kept separate so the
    home feed can batch every curation's card load into one query.
    """
    cache_key = f"curation:{curation.id}:spots"
    cached = await redis.get(cache_key)
    # None = miss; "" = cached-empty (don't re-resolve empty curations every request)
    if cached is not None:
        return cached.split(",") if cached else []

    handpicked = await _handpicked_ids(session, curation.id)
    if handpicked:
        ids = handpicked[:_SHOW]
    else:
        pool = await _pool_ids(session, curation)
        ids = _seed_pick(curation.id, pool)
    ttl = seconds_until_kst_midnight(kst_now()) + _jitter(curation.id)
    await redis.set(cache_key, ",".join(ids), ex=ttl)
    return ids


async def resolve_curation_spots(
    session: AsyncSession,
    redis: Redis,
    curation: CurationRow,
) -> list[SpotCardRow]:
    """Resolve + hydrate a curation's display spots (handpicked, else quality-gate pool).

    Returns ordered SpotCardRows, max 8 per path. Resolved ids are cached daily.
    """
    ids = await resolve_curation_ids(session, redis, curation)
    if not ids:
        return []
    by_id = await load_spot_cards_by_ids(session, ids)
    # Preserve the resolved order; drop ids that no longer hydrate.
    return [by_id[cid] for cid in ids if cid in by_id]


async def get_curation_detail(
    session: AsyncSession,
    redis: Redis,
    slug: str,
) -> CurationDetailRow:
    """Resolve a published curation by slug to its detail projection (S09 §5.2).

    Raises ResourceNotFound when the slug is unknown or unpublished.
    """
    row = (
        await session.execute(
            select(Curation).where(
                Curation.slug == slug,
                Curation.is_published.is_(True),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise ResourceNotFound()

    cur = _to_row(row)
    resolved = await resolve_curation_spots(session, redis, cur)
    congestion = await load_congestion(session, [r.content_id for r in resolved])
    for r in resolved:
        r.congestion = congestion.get(r.content_id)

    return CurationDetailRow(
        id=cur.id,
        type=cur.type,
        slug=cur.slug,
        title=cur.title,
        lead=cur.lead,
        intro=cur.intro,
        cover_url=await cover_url(session, cur.cover_spot_id, resolved),
        spots=resolved,
    )
