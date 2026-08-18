from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.spots.models import LclsSystmCode, Region, Sigungu, Spot, SpotDetail
from app.modules.spots.services.nearby import NearbyCategory, category_predicate, derive_category
from app.modules.spots.services.rows import SpotCardRow


def image_bearing_spots_stmt(*, since: datetime | None = None) -> Select[tuple[str, str | None]]:
    stmt = select(Spot.content_id, Spot.first_image_url).where(
        Spot.first_image_url.is_not(None),
        Spot.first_image_url != "",
    )
    if since is not None:
        stmt = stmt.where(Spot.synced_at >= since)
    return stmt


def attraction_image_spots_stmt() -> Select[tuple[str, str | None]]:
    return image_bearing_spots_stmt().where(
        Spot.show_flag == 1,
        category_predicate(NearbyCategory.attraction),
    )


async def lock_current_spot_image(session: AsyncSession, content_id: str, image_url: str) -> bool:
    locked_content_id = await session.scalar(
        select(Spot.content_id)
        .where(Spot.content_id == content_id, Spot.first_image_url == image_url)
        .with_for_update()
    )
    return locked_content_id is not None


async def load_region_meta(
    session: AsyncSession,
    content_ids: list[str],
) -> dict[str, tuple[str | None, str | None]]:
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
    if not content_ids:
        return {}
    result = await session.execute(
        select(SpotDetail.content_id, SpotDetail.overview).where(
            SpotDetail.content_id.in_(content_ids)
        )
    )
    return {row.content_id: row.overview for row in result}


async def load_spot_cards_by_ids(
    session: AsyncSession,
    content_ids: list[str],
) -> dict[str, SpotCardRow]:
    rows = await _load_spot_cards(session, content_ids)
    return {r.content_id: r for r in rows}


async def load_active_spot_cards_by_ids(
    session: AsyncSession,
    content_ids: list[str],
) -> dict[str, SpotCardRow]:
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
            Spot.cpyrht_div_cd,
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
            cpyrht_div_cd=r.cpyrht_div_cd,
        )
        for r in rows
    }


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
