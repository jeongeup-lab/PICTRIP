from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import async_session_factory
from app.core.logging import get_logger
from app.kto.client import KtoClient
from app.modules.spots.models import Spot, SpotDetail
from app.modules.spots.services import (
    attraction_image_spots_stmt,
    fetch_detail_common,
    persist_detail_common,
)
from app.web.errors import KtoQuotaExhausted

logger = get_logger(__name__)

WRITTEN = "written"
KTO_FAILED = "kto_failed"
EMPTY = "empty_overview"
QUOTA_SKIPPED = "quota_skipped"


@dataclass
class PrewarmResult:
    written: int = 0
    failed: int = 0
    by_status: dict[str, int] = field(default_factory=dict)

    def record(self, status: str) -> None:
        self.by_status[status] = self.by_status.get(status, 0) + 1
        if status == WRITTEN:
            self.written += 1
        elif status == KTO_FAILED:
            self.failed += 1


async def collect_prewarm_targets(
    session: AsyncSession, *, limit: int | None = None
) -> list[tuple[str, int]]:
    spots = attraction_image_spots_stmt().subquery()
    cached = select(SpotDetail.content_id).where(
        SpotDetail.content_id == spots.c.content_id,
        SpotDetail.overview.is_not(None),
        SpotDetail.overview != "",
    )
    stmt = (
        select(spots.c.content_id, Spot.content_type_id)
        .join(Spot, Spot.content_id == spots.c.content_id)
        .where(~cached.exists())
        .order_by(spots.c.content_id)
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    rows = await session.execute(stmt)
    return [(str(content_id), int(content_type_id)) for content_id, content_type_id in rows]


async def _prewarm_one(
    session: AsyncSession, kto: KtoClient, content_id: str, content_type_id: int
) -> str:
    try:
        overview, homepage, tel = await fetch_detail_common(kto, content_id)
    except KtoQuotaExhausted:
        raise
    except Exception as exc:
        logger.warning(
            "spot.prewarm.kto_failed", content_id=content_id, error_type=type(exc).__name__
        )
        return KTO_FAILED
    if not overview:
        return EMPTY
    await persist_detail_common(session, content_id, content_type_id, overview, homepage, tel)
    return WRITTEN


async def run_prewarm_job(*, limit: int, pause_seconds: float = 0.0) -> PrewarmResult:
    result = PrewarmResult()
    kto = KtoClient()
    try:
        async with async_session_factory() as session:
            targets = await collect_prewarm_targets(session, limit=limit)
            logger.info("spot.prewarm.start", targets=len(targets))
            for index, (content_id, content_type_id) in enumerate(targets):
                try:
                    result.record(await _prewarm_one(session, kto, content_id, content_type_id))
                except KtoQuotaExhausted:
                    remaining = len(targets) - index
                    logger.warning("spot.prewarm.quota_exhausted", remaining=remaining)
                    for _ in range(remaining):
                        result.record(QUOTA_SKIPPED)
                    break
                if pause_seconds:
                    await asyncio.sleep(pause_seconds)
    finally:
        await kto.aclose()
    logger.info("spot.prewarm.done", written=result.written, failed=result.failed)
    return result
