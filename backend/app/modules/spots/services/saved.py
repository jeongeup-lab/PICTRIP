"""Saved spots / bookmarks (ADR-0011). user_saved_spots FKs spots.content_id, so
its DB access stays in SPT; USR routes call these via the service seam."""

from __future__ import annotations

import base64
import binascii
from datetime import datetime

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ResourceNotFound, ValidationFailed
from app.modules.spots.models import LclsSystmCode, Spot, UserSavedSpot
from app.modules.spots.services.rows import SpotCardRow

# Opaque keyset cursor on (saved_at, content_id) DESC, base64-encoded. The pair
# is unique (content_id is the PK tail) so the sort is total and resume is exact.
_CURSOR_SEP = "\x1f"


def encode_saved_cursor(saved_at: datetime, content_id: str) -> str:
    raw = f"{saved_at.isoformat()}{_CURSOR_SEP}{content_id}".encode()
    return base64.urlsafe_b64encode(raw).decode("ascii")


def decode_saved_cursor(cursor: str) -> tuple[datetime, str]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
        iso, content_id = raw.split(_CURSOR_SEP, 1)
        return datetime.fromisoformat(iso), content_id
    except (binascii.Error, UnicodeDecodeError, ValueError) as e:
        raise ValidationFailed("커서 형식이 올바르지 않습니다.") from e


async def save_spot(session: AsyncSession, *, user_id: int, content_id: str) -> bool:
    """Idempotent save. True if inserted, False if already saved. 404 if no spot."""
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
    """Idempotent unsave. True if a row was removed, False if nothing to remove."""
    stmt = (
        delete(UserSavedSpot)
        .where(UserSavedSpot.user_id == user_id, UserSavedSpot.content_id == content_id)
        .returning(UserSavedSpot.content_id)
    )
    removed = await session.scalar(stmt)
    await session.commit()
    return removed is not None


async def list_saved_spots(
    session: AsyncSession,
    *,
    user_id: int,
    limit: int = 24,
    cursor: str | None = None,
) -> tuple[list[SpotCardRow], str | None, bool]:
    """User's saved spots as cards, newest first. Keyset on (saved_at, content_id)
    DESC. Returns (rows, next_cursor, has_more); next_cursor None on the last page."""
    stmt = (
        select(
            Spot.content_id,
            Spot.title,
            Spot.first_image_url,
            Spot.addr1,
            Spot.mapx,
            Spot.mapy,
            LclsSystmCode.lcls_systm3_nm,
            UserSavedSpot.saved_at,
        )
        .join(UserSavedSpot, UserSavedSpot.content_id == Spot.content_id)
        .outerjoin(LclsSystmCode, LclsSystmCode.lcls_systm3_cd == Spot.lcls_systm3)
        .where(UserSavedSpot.user_id == user_id, Spot.show_flag == 1)
    )
    if cursor is not None:
        c_saved_at, c_content_id = decode_saved_cursor(cursor)
        # Strictly after the cursor in DESC order: older saved_at, or equal with smaller content_id.
        stmt = stmt.where(
            or_(
                UserSavedSpot.saved_at < c_saved_at,
                and_(
                    UserSavedSpot.saved_at == c_saved_at,
                    UserSavedSpot.content_id < c_content_id,
                ),
            )
        )
    stmt = stmt.order_by(UserSavedSpot.saved_at.desc(), UserSavedSpot.content_id.desc()).limit(
        limit + 1
    )

    rows = (await session.execute(stmt)).all()
    has_more = len(rows) > limit
    page = rows[:limit]
    cards = [
        SpotCardRow(
            content_id=r.content_id,
            title=r.title,
            first_image_url=r.first_image_url,
            addr1=r.addr1,
            mapx=float(r.mapx) if r.mapx is not None else None,
            mapy=float(r.mapy) if r.mapy is not None else None,
            lcls_systm3_nm=r.lcls_systm3_nm,
        )
        for r in page
    ]
    next_cursor = (
        encode_saved_cursor(page[-1].saved_at, page[-1].content_id) if has_more and page else None
    )
    return cards, next_cursor, has_more
