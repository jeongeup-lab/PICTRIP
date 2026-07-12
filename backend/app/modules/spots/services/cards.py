"""Spot-card loaders — id → SpotCardRow hydration seams for other modules."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.spots.models import LclsSystmCode, Region, Sigungu, Spot, SpotDetail
from app.modules.spots.services.nearby import derive_category
from app.modules.spots.services.rows import SpotCardRow


def image_bearing_spots_stmt(*, since: datetime | None = None) -> Select[tuple[str, str | None]]:
    """(content_id, first_image_url) selectable for spots with a non-empty image URL.

    Cross-module contract for the images embedding job: images composes its own
    embedding/failure filters against this selectable (as a subquery) so Spot ORM
    knowledge stays inside spots. ``since`` scopes to spots synced at or after it.
    """
    stmt = select(Spot.content_id, Spot.first_image_url).where(
        Spot.first_image_url.is_not(None),
        Spot.first_image_url != "",
    )
    if since is not None:
        stmt = stmt.where(Spot.synced_at >= since)
    return stmt


async def load_region_meta(
    session: AsyncSession,
    content_ids: list[str],
) -> dict[str, tuple[str | None, str | None]]:
    """{content_id: (region_name, sigungu_name)} for a batch of ids; missing ids absent."""
    if not content_ids:
        return {}
    stmt = (
        select(
            Spot.content_id,
            Region.ldong_regn_nm,
            Sigungu.ldong_signgu_nm,
        )
        .outerjoin(Region, Region.ldong_regn_cd == Spot.ldong_regn_cd)
        .outerjoin(Sigungu, Sigungu.ldong_signgu_cd == Spot.ldong_signgu_cd)
        .where(Spot.content_id.in_(content_ids))
    )
    rows = (await session.execute(stmt)).all()
    return {r.content_id: (r.ldong_regn_nm, r.ldong_signgu_nm) for r in rows}


async def load_overview_map(
    session: AsyncSession,
    content_ids: Sequence[str],
) -> dict[str, str | None]:
    """{content_id: overview} for a batch of ids; missing ids absent. overview lives
    on spot_details (KTO verbatim), the cross-module seam for match-card previews."""
    if not content_ids:
        return {}
    result = await session.execute(
        select(SpotDetail.content_id, SpotDetail.overview).where(
            SpotDetail.content_id.in_(content_ids)
        )
    )
    return {row.content_id: row.overview for row in result}


async def cover_url(
    session: AsyncSession,
    cover_spot_id: str | None,
    resolved: list[SpotCardRow],
) -> str | None:
    """coverUrl = cover spot's image, else first resolved spot's, else None.
    Lives here (not feed/curations) to avoid the feed->curations circular import.

    Active-only (show_flag=1), same policy as ``load_cover_images``: a cover spot
    hidden after being set must not keep serving its image — fall back instead.
    """
    if cover_spot_id is not None:
        img = (
            await session.execute(
                select(Spot.first_image_url).where(
                    Spot.content_id == cover_spot_id, Spot.show_flag == 1
                )
            )
        ).scalar_one_or_none()
        if img:
            return img
    for r in resolved:
        if r.first_image_url:
            return r.first_image_url
    return None


async def load_cover_images(
    session: AsyncSession,
    content_ids: list[str],
) -> dict[str, str | None]:
    """{content_id: first_image_url} for cover-spot lookups; missing ids absent.
    Lets the feed batch every hero's cover image into a single query.

    Active-only (show_flag=1): a cover spot hidden after being set must not keep
    serving its image — the feed's cover fallback / hero-drop defense takes over.
    """
    if not content_ids:
        return {}
    rows = (
        await session.execute(
            select(Spot.content_id, Spot.first_image_url).where(
                Spot.content_id.in_(content_ids), Spot.show_flag == 1
            )
        )
    ).all()
    return {r.content_id: r.first_image_url for r in rows}


async def load_spot_cards_by_ids(
    session: AsyncSession,
    content_ids: list[str],
) -> dict[str, SpotCardRow]:
    """{content_id: SpotCardRow}; missing ids absent. Public seam for other modules."""
    rows = await _load_spot_cards(session, content_ids)
    return {r.content_id: r for r in rows}


async def load_active_spot_cards_by_ids(
    session: AsyncSession,
    content_ids: list[str],
) -> dict[str, SpotCardRow]:
    """Like load_spot_cards_by_ids but active-only (show_flag=1). Lets CRS diff
    requested vs returned ids to reject unknown/inactive spots before the
    RESTRICT FK on course_items.content_id would trip."""
    if not content_ids:
        return {}
    stmt = (
        select(
            Spot.content_id,
            Spot.title,
            Spot.first_image_url,
            Spot.addr1,
            Spot.mapx,
            Spot.mapy,
            Spot.lcls_systm1,
            Spot.lcls_systm2,
            Spot.lcls_systm3,
            LclsSystmCode.lcls_systm3_nm,
        )
        .outerjoin(LclsSystmCode, LclsSystmCode.lcls_systm3_cd == Spot.lcls_systm3)
        .where(Spot.content_id.in_(content_ids), Spot.show_flag == 1)
    )
    rows = (await session.execute(stmt)).all()
    return {
        r.content_id: SpotCardRow(
            content_id=r.content_id,
            title=r.title,
            first_image_url=r.first_image_url,
            addr1=r.addr1,
            mapx=float(r.mapx) if r.mapx is not None else None,
            mapy=float(r.mapy) if r.mapy is not None else None,
            category=derive_category(r.lcls_systm1, r.lcls_systm2, r.lcls_systm3),
            lcls_systm3_nm=r.lcls_systm3_nm,
        )
        for r in rows
    }


async def load_exposable_spot_cards_by_ids(
    session: AsyncSession,
    content_ids: list[str],
) -> dict[str, SpotCardRow]:
    """Active AND image-bearing cards — the curation serving gate (A11).

    Mirrors the handpick/pool registration gate (show_flag=1 + non-empty image)
    so a spot hidden OR stripped of its image after the day-cache was built still
    won't render until the cache expires at KST midnight. CRS uses the plain
    active loader instead — a course item may be an imageless spot.
    """
    by_id = await load_active_spot_cards_by_ids(session, content_ids)
    return {cid: card for cid, card in by_id.items() if card.first_image_url}


async def _load_spot_card(session: AsyncSession, content_id: str) -> SpotCardRow | None:
    stmt = (
        select(
            Spot.content_id,
            Spot.title,
            Spot.first_image_url,
            Spot.addr1,
            Spot.mapx,
            Spot.mapy,
            LclsSystmCode.lcls_systm3_nm,
        )
        .outerjoin(LclsSystmCode, LclsSystmCode.lcls_systm3_cd == Spot.lcls_systm3)
        .where(Spot.content_id == content_id)
    )
    row = (await session.execute(stmt)).first()
    if row is None:
        return None
    return SpotCardRow(
        content_id=row.content_id,
        title=row.title,
        first_image_url=row.first_image_url,
        addr1=row.addr1,
        mapx=float(row.mapx) if row.mapx is not None else None,
        mapy=float(row.mapy) if row.mapy is not None else None,
        lcls_systm3_nm=row.lcls_systm3_nm,
    )


async def _load_spot_cards(session: AsyncSession, content_ids: list[str]) -> list[SpotCardRow]:
    if not content_ids:
        return []
    stmt = (
        select(
            Spot.content_id,
            Spot.title,
            Spot.first_image_url,
            Spot.addr1,
            Spot.mapx,
            Spot.mapy,
            LclsSystmCode.lcls_systm3_nm,
        )
        .outerjoin(LclsSystmCode, LclsSystmCode.lcls_systm3_cd == Spot.lcls_systm3)
        .where(Spot.content_id.in_(content_ids))
    )
    rows = (await session.execute(stmt)).all()
    return [
        SpotCardRow(
            content_id=r.content_id,
            title=r.title,
            first_image_url=r.first_image_url,
            addr1=r.addr1,
            mapx=float(r.mapx) if r.mapx is not None else None,
            mapy=float(r.mapy) if r.mapy is not None else None,
            lcls_systm3_nm=r.lcls_systm3_nm,
        )
        for r in rows
    ]
