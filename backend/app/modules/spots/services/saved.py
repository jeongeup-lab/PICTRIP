"""Saved spots / bookmarks (ADR-0011).

The ``user_saved_spots`` join table lives in SPT (it FKs ``spots.content_id``),
so all of its DB access stays here even though the collection is user-owned;
USR routes call these via the service seam.
"""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ResourceNotFound
from app.modules.spots.models import Spot, UserSavedSpot
from app.modules.spots.services.rows import SpotCardRow


async def save_spot(session: AsyncSession, *, user_id: int, content_id: str) -> bool:
    """Idempotent save. Returns True if a new row was inserted, False if the
    spot was already saved. Raises ResourceNotFound if the spot doesn't exist."""
    exists = await session.scalar(
        select(Spot.content_id).where(Spot.content_id == content_id, Spot.show_flag == 1)
    )
    if exists is None:
        raise ResourceNotFound("해당 관광지를 찾을 수 없습니다.")

    stmt = (
        pg_insert(UserSavedSpot)
        .values(user_id=user_id, content_id=content_id)
        .on_conflict_do_nothing(index_elements=["user_id", "content_id"])
        .returning(UserSavedSpot.content_id)
    )
    inserted = await session.scalar(stmt)
    await session.commit()
    return inserted is not None


async def unsave_spot(session: AsyncSession, *, user_id: int, content_id: str) -> bool:
    """Idempotent unsave. Returns True if a row was removed, False if there was
    nothing to remove."""
    stmt = (
        delete(UserSavedSpot)
        .where(UserSavedSpot.user_id == user_id, UserSavedSpot.content_id == content_id)
        .returning(UserSavedSpot.content_id)
    )
    removed = await session.scalar(stmt)
    await session.commit()
    return removed is not None


async def list_saved_spots(
    session: AsyncSession, *, user_id: int, limit: int = 100
) -> list[SpotCardRow]:
    """User's saved spots as spot cards, newest-saved first."""
    stmt = (
        select(
            Spot.content_id,
            Spot.title,
            Spot.first_image_url,
            Spot.addr1,
            Spot.mapx,
            Spot.mapy,
        )
        .join(UserSavedSpot, UserSavedSpot.content_id == Spot.content_id)
        .where(UserSavedSpot.user_id == user_id, Spot.show_flag == 1)
        .order_by(UserSavedSpot.saved_at.desc())
        .limit(limit)
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
        )
        for r in rows
    ]
