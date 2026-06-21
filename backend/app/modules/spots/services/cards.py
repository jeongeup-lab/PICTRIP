"""Spot-card loaders — id → SpotCardRow hydration seams for other modules."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.spots.models import Spot
from app.modules.spots.services.nearby import derive_category
from app.modules.spots.services.rows import SpotCardRow


async def load_spot_cards_by_ids(
    session: AsyncSession,
    content_ids: list[str],
) -> dict[str, SpotCardRow]:
    """Resolve a list of content_ids to SpotCardRow summaries, keyed by id.

    Public seam for other modules (e.g. TST photo-search) that already hold a
    list of nearest content_ids and need SPT metadata without reaching into
    SPT models. Missing/inactive ids are simply absent from the result.
    """
    rows = await _load_spot_cards(session, content_ids)
    return {r.content_id: r for r in rows}


async def load_active_spot_cards_by_ids(
    session: AsyncSession,
    content_ids: list[str],
) -> dict[str, SpotCardRow]:
    """Like ``load_spot_cards_by_ids`` but restricted to active (show_flag=1)
    spots, keyed by content_id.

    Public seam for CRS course persistence: validate + hydrate a list of
    content_ids in one query without reaching into SPT models. Missing or hidden
    ids are simply absent from the result, so the caller can diff the requested
    ids against the returned keys to reject unknown/inactive spots *before* an
    insert that would otherwise trip the RESTRICT FK on
    ``course_items.content_id``.
    """
    if not content_ids:
        return {}
    stmt = select(
        Spot.content_id,
        Spot.title,
        Spot.first_image_url,
        Spot.addr1,
        Spot.mapx,
        Spot.mapy,
        Spot.lcls_systm1,
        Spot.lcls_systm2,
        Spot.lcls_systm3,
    ).where(Spot.content_id.in_(content_ids), Spot.show_flag == 1)
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
        )
        for r in rows
    }


async def _load_spot_card(session: AsyncSession, content_id: str) -> SpotCardRow | None:
    stmt = select(
        Spot.content_id,
        Spot.title,
        Spot.first_image_url,
        Spot.addr1,
        Spot.mapx,
        Spot.mapy,
    ).where(Spot.content_id == content_id)
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
    )


async def _load_spot_cards(session: AsyncSession, content_ids: list[str]) -> list[SpotCardRow]:
    if not content_ids:
        return []
    stmt = select(
        Spot.content_id,
        Spot.title,
        Spot.first_image_url,
        Spot.addr1,
        Spot.mapx,
        Spot.mapy,
    ).where(Spot.content_id.in_(content_ids))
    rows = (await session.execute(stmt)).all()
    return [
        SpotCardRow(
            content_id=r.content_id,
            title=r.title,
            first_image_url=r.first_image_url,
            addr1=r.addr1,
            mapx=float(r.mapx) if r.mapx is not None else None,
            mapy=float(r.mapy) if r.mapy is not None else None,
        )
        for r in rows
    ]
