"""Curation resolution — handpicked spots or the quality-gate random pool.

A curation's display spots come from one of two sources:

1. **Handpicked** — rows in ``curation_spots`` ordered by ``position``.
2. **Quality-gate random pool** (S07 §3.3) — when a curation has no handpicks,
   draw from active, image-bearing spots scoped by the curation's ``region_cd``
   (region type) or ``mood_id`` (mood type), ranked by quality signals
   (overview present, embedding present), then deterministically pick/rotate 8
   by a per-curation + per-KST-date hash seed.

The resolved ``content_id`` list is cached in ``curation:{id}:spots`` until the
next KST midnight plus a *stable* per-curation jitter (0..600s) so the whole
feed does not expire simultaneously (thundering-herd avoidance). Determinism
uses ``hashlib`` (not the salted builtin ``hash()``) so it is stable across
processes.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from redis.asyncio import Redis
from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import kst_now, seconds_until_kst_midnight
from app.modules.images.models import SpotEmbedding
from app.modules.spots.models import Curation, CurationSpot, Spot, SpotDetail, SpotMood
from app.modules.spots.services.cards import load_spot_cards_by_ids
from app.modules.spots.services.rows import SpotCardRow

# Size of the candidate pool before the deterministic pick, and how many to show.
_POOL_LIMIT = 30
_SHOW = 8
_JITTER_MAX = 601  # 0..600 inclusive


@dataclass
class CurationRow:
    """Lightweight curation projection for the feed (no ORM leakage to routes)."""

    id: int
    type: str
    slug: str
    title: str
    subtitle: str | None
    region_cd: str | None
    mood_id: int | None
    cover_spot_id: str | None
    position: int


def _jitter(curation_id: int) -> int:
    """Stable per-curation cache jitter in 0..600s (NOT random)."""
    return curation_id % _JITTER_MAX


def _seed_pick(curation_id: int, ordered_ids: list[str]) -> list[str]:
    """Deterministically pick/rotate up to ``_SHOW`` ids.

    Same ``curation_id`` + same KST date yields the same selection. Uses a
    rotation offset derived from a stable sha256 of ``curation_id|YYYY-MM-DD``
    so the daily feed shifts but is reproducible across processes.
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
    return [
        CurationRow(
            id=r.id,
            type=r.type,
            slug=r.slug,
            title=r.title,
            subtitle=r.subtitle,
            region_cd=r.region_cd,
            mood_id=r.mood_id,
            cover_spot_id=r.cover_spot_id,
            position=r.position,
        )
        for r in rows
    ]


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

    Metadata query against ``idx_spots_image_pool`` (``show_flag = 1 AND
    first_image_url IS NOT NULL`` partial index). Quality ranking uses EXISTS
    subqueries — never a JOIN/CTE against the HNSW index.
    """
    has_overview = exists().where(SpotDetail.content_id == Spot.content_id)
    has_embedding = exists().where(SpotEmbedding.content_id == Spot.content_id)

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


async def resolve_curation_spots(
    session: AsyncSession,
    redis: Redis,
    curation: CurationRow,
) -> list[SpotCardRow]:
    """Resolve a curation's display spots (handpicked, else quality-gate pool).

    Returns ordered ``SpotCardRow``s (max 8 for the pool path; handpicks are
    returned in full ``position`` order). The resolved content_id list is cached
    daily in ``curation:{id}:spots``.
    """
    cache_key = f"curation:{curation.id}:spots"
    cached = await redis.get(cache_key)
    if cached:
        ids = cached.split(",") if cached else []
    else:
        handpicked = await _handpicked_ids(session, curation.id)
        if handpicked:
            ids = handpicked
        else:
            pool = await _pool_ids(session, curation)
            ids = _seed_pick(curation.id, pool)
        ttl = seconds_until_kst_midnight(kst_now()) + _jitter(curation.id)
        await redis.set(cache_key, ",".join(ids), ex=ttl)

    if not ids:
        return []
    by_id = await load_spot_cards_by_ids(session, ids)
    # Preserve the resolved order; drop ids that no longer hydrate.
    return [by_id[cid] for cid in ids if cid in by_id]
