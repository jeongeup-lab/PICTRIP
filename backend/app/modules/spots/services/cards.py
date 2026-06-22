"""Spot-card loaders — id → SpotCardRow hydration seams for other modules."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.spots.models import LclsSystmCode, Region, Sigungu, Spot, SpotConcentration
from app.modules.spots.services.nearby import derive_category
from app.modules.spots.services.rows import SpotCardRow


def bucket_congestion(rate: float | None) -> str | None:
    """Bucket a KTO 집중률 (0-100) into the card's congestion label.

    Boundaries are inclusive at the seams: ``rate < 34 -> "low"``,
    ``34 <= rate <= 66 -> "medium"``, ``rate > 66 -> "high"``, ``None -> None``.
    """
    if rate is None:
        return None
    if rate < 34:
        return "low"
    if rate <= 66:
        return "medium"
    return "high"


async def load_congestion(
    session: AsyncSession,
    content_ids: list[str],
) -> dict[str, str | None]:
    """Bucket the preserved ``spot_concentration`` rate for each content_id.

    Returns ``{content_id: "low"|"medium"|"high"}`` keyed only by ids that have a
    row; misses are absent so the caller defaults them to ``None`` (omit-friendly,
    matching the canonical card's optional ``congestion``). Shared enrichment seam
    for Tasks 10-17.
    """
    if not content_ids:
        return {}
    rows = (
        await session.execute(
            select(
                SpotConcentration.content_id,
                SpotConcentration.concentration_rate,
            ).where(SpotConcentration.content_id.in_(content_ids))
        )
    ).all()
    return {cid: bucket_congestion(float(rate)) for cid, rate in rows}


async def load_region_meta(
    session: AsyncSession,
    content_ids: list[str],
) -> dict[str, tuple[str | None, str | None]]:
    """Resolve ``{content_id: (region_name, sigungu_name)}`` for a batch of ids.

    Shared enrichment seam (e.g. TST photo-search) — joins ``spots`` to
    ``regions``/``sigungus`` by legal-dong code in one query. Ids with no
    region/sigungu code (or no matching row) map to ``(None, None)`` /
    a half-filled tuple; missing ids are simply absent.
    """
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
    """coverUrl = cover spot's firstImageUrl, else first resolved spot's, else None.

    Shared by the home feed (heroes) and curation detail. Lives here (both already
    import from ``cards``) to avoid the feed→curations circular import that the
    earlier per-module duplication worked around.
    """
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
