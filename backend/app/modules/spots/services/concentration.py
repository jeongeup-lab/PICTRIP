"""집중률 서빙 쿼리 — Hot(붐비는) / Hidden(조용하지만 볼거리) 채널 시드."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.spots.models import Spot, SpotConcentration, SpotDetail
from app.modules.spots.services.cards import load_region_meta


@dataclass(frozen=True)
class ConcentrationCardRow:
    content_id: str
    title: str
    first_image_url: str
    region_label: str
    rank: int


async def load_hot_spots(session: AsyncSession, *, limit: int = 10) -> list[ConcentrationCardRow]:
    return await _load(session, limit=limit, ascending=False, require_overview=False)


async def load_hidden_spots(
    session: AsyncSession, *, limit: int = 10
) -> list[ConcentrationCardRow]:
    return await _load(session, limit=limit, ascending=True, require_overview=True)


async def _load(
    session: AsyncSession,
    *,
    limit: int,
    ascending: bool,
    require_overview: bool,
) -> list[ConcentrationCardRow]:
    order = (
        SpotConcentration.concentration_rate.asc()
        if ascending
        else SpotConcentration.concentration_rate.desc()
    )
    stmt = (
        select(Spot.content_id, Spot.title, Spot.first_image_url)
        .join(SpotConcentration, SpotConcentration.content_id == Spot.content_id)
        .where(
            Spot.show_flag == 1,
            Spot.first_image_url.is_not(None),
            Spot.first_image_url != "",
        )
    )
    if require_overview:
        stmt = stmt.join(SpotDetail, SpotDetail.content_id == Spot.content_id).where(
            SpotDetail.overview.is_not(None),
            SpotDetail.overview != "",
        )
    stmt = stmt.order_by(order, Spot.content_id.asc()).limit(limit)

    rows = (await session.execute(stmt)).all()
    meta = await load_region_meta(session, [r.content_id for r in rows])
    return [
        ConcentrationCardRow(
            content_id=r.content_id,
            title=r.title,
            first_image_url=r.first_image_url,
            region_label=_region_label(meta.get(r.content_id, (None, None))),
            rank=idx,
        )
        for idx, r in enumerate(rows, start=1)
    ]


def _region_label(meta: tuple[str | None, str | None]) -> str:
    return " ".join(part for part in meta if part)
