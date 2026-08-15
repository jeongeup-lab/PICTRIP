from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.feed import repositories
from app.modules.feed.repositories import ShortRow, ShortSpotRow
from app.modules.spots.services import load_region_meta
from app.web.errors import ValidationFailed


@dataclass(frozen=True)
class ShortsPageRow:
    items: list[ShortRow]
    spots_by_video: dict[str, list[ShortSpotRow]]
    region_by_content: dict[str, tuple[str | None, str | None]]
    next_cursor: str | None
    has_more: bool


def _decode_cursor(cursor: str | None) -> int | None:
    if not cursor:
        return None
    try:
        return int(cursor)
    except ValueError as exc:
        raise ValidationFailed("invalid cursor") from exc


async def list_shorts(session: AsyncSession, *, cursor: str | None, limit: int) -> ShortsPageRow:
    cursor_rank = _decode_cursor(cursor)
    rows = await repositories.fetch_shorts_page(session, cursor_rank=cursor_rank, limit=limit + 1)
    has_more = len(rows) > limit
    page = rows[:limit]
    spots_by_video = await repositories.fetch_shorts_spots(session, [row.video_id for row in page])
    content_ids = [spot.content_id for spots in spots_by_video.values() for spot in spots]
    region_by_content = await load_region_meta(session, content_ids)
    next_cursor = str(page[-1].rank) if page and has_more else None
    return ShortsPageRow(
        items=page,
        spots_by_video=spots_by_video,
        region_by_content=region_by_content,
        next_cursor=next_cursor,
        has_more=has_more,
    )
