"""Spot-card loaders — id → SpotCardRow hydration seams for other modules."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.spots.models import LclsSystmCode, Region, Sigungu, Spot
from app.modules.spots.services.nearby import derive_category
from app.modules.spots.services.rows import SpotCardRow


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


async def cover_url(
    session: AsyncSession,
    cover_spot_id: str | None,
    resolved: list[SpotCardRow],
) -> str | None:
    """coverUrl = cover spot's image, else first resolved spot's, else None.
    Lives here (not feed/curations) to avoid the feed->curations circular import."""
    if cover_spot_id is not None:
        img = (
            await session.execute(
                select(Spot.first_image_url).where(Spot.content_id == cover_spot_id)
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
    Lets the feed batch every hero's cover image into a single query."""
    if not content_ids:
        return {}
    rows = (
        await session.execute(
            select(Spot.content_id, Spot.first_image_url).where(Spot.content_id.in_(content_ids))
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
