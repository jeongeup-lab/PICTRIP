from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime

import httpx
from sqlalchemy import delete, func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.db import async_session_factory
from app.core.embedding import embedder
from app.core.logging import get_logger
from app.modules.images.models import EmbeddingFailure, SpotEmbedding

logger = get_logger(__name__)

_embed_lock = asyncio.Lock()

OK = "ok"
DOWNLOAD_FAILED = "download_failed"
CLIP_ERROR = "clip_error"
SOURCE_CHANGED = "source_changed"


@dataclass
class EmbedResult:
    written: int = 0
    failed: int = 0
    skipped: int = 0
    by_status: dict[str, int] = field(default_factory=dict)

    def record(self, status: str) -> None:
        self.by_status[status] = self.by_status.get(status, 0) + 1
        if status == OK:
            self.written += 1
        elif status == SOURCE_CHANGED:
            self.skipped += 1
        else:
            self.failed += 1


async def collect_targets(
    session: AsyncSession,
    *,
    only_failed: bool = False,
    failure_reason: str | None = None,
    since: datetime | None = None,
    limit: int | None = None,
) -> list[tuple[str, str]]:
    from app.modules.spots.services import image_bearing_spots_stmt

    spots = image_bearing_spots_stmt(since=since).subquery()
    has_current_embedding = select(SpotEmbedding.content_id).where(
        SpotEmbedding.content_id == spots.c.content_id,
        SpotEmbedding.image_url == spots.c.first_image_url,
    )
    stmt = (
        select(spots.c.content_id, spots.c.first_image_url)
        .where(~has_current_embedding.exists())
        .order_by(spots.c.content_id)
    )
    if only_failed or failure_reason is not None:
        has_failure = select(EmbeddingFailure.content_id).where(
            EmbeddingFailure.content_id == spots.c.content_id
        )
        if failure_reason is not None:
            has_failure = has_failure.where(EmbeddingFailure.reason == failure_reason)
        stmt = stmt.where(has_failure.exists())
    if limit:
        stmt = stmt.limit(limit)
    rows = (await session.execute(stmt)).all()
    return [(cid, url) for cid, url in rows]


async def _embed_one(
    content_id: str,
    image_url: str,
    client: httpx.AsyncClient,
    dl_sem: asyncio.Semaphore,
) -> tuple[str, str, list[float] | None, str, str | None]:
    try:
        async with dl_sem:
            resp = await client.get(image_url, timeout=20.0, follow_redirects=True)
        if resp.status_code != 200 or not resp.content:
            return (content_id, image_url, None, DOWNLOAD_FAILED, f"HTTP {resp.status_code}")
        async with _embed_lock:
            vector = await asyncio.to_thread(embedder.embed_image, resp.content)
        return (content_id, image_url, vector, OK, None)
    except Exception as exc:
        logger.warning("embed.failed", content_id=content_id, error=str(exc))
        return (content_id, image_url, None, CLIP_ERROR, str(exc)[:500])


async def _record_success(
    session: AsyncSession, content_id: str, image_url: str, vector: list[float]
) -> bool:
    from app.modules.spots.services import lock_current_spot_image

    if not await lock_current_spot_image(session, content_id, image_url):
        return False
    stmt = (
        pg_insert(SpotEmbedding)
        .values(content_id=content_id, embedding=vector, image_url=image_url)
        .on_conflict_do_update(
            index_elements=["content_id"],
            set_={"embedding": vector, "image_url": image_url, "computed_at": func.now()},
        )
    )
    await session.execute(stmt)
    await session.execute(delete(EmbeddingFailure).where(EmbeddingFailure.content_id == content_id))
    return True


async def _record_failure(
    session: AsyncSession,
    content_id: str,
    image_url: str,
    reason: str,
    detail: str | None,
) -> bool:
    from app.modules.spots.services import lock_current_spot_image

    if not await lock_current_spot_image(session, content_id, image_url):
        return False
    stmt = (
        pg_insert(EmbeddingFailure)
        .values(content_id=content_id, reason=reason, attempts=1, last_error=detail)
        .on_conflict_do_update(
            index_elements=["content_id"],
            set_={
                "reason": reason,
                "last_error": detail,
                "attempts": EmbeddingFailure.attempts + 1,
                "last_attempt_at": func.now(),
            },
        )
    )
    await session.execute(stmt)
    return True


async def embed_spots(
    session: AsyncSession,
    targets: list[tuple[str, str]],
    *,
    client: httpx.AsyncClient,
    dl_sem: asyncio.Semaphore,
    result: EmbedResult | None = None,
) -> EmbedResult:
    result = result or EmbedResult()
    if not targets:
        return result

    outcomes = await asyncio.gather(*(_embed_one(cid, url, client, dl_sem) for cid, url in targets))
    for content_id, image_url, vector, status, detail in outcomes:
        if status == OK and vector is not None:
            written = await _record_success(session, content_id, image_url, vector)
            result.record(OK if written else SOURCE_CHANGED)
        else:
            recorded = await _record_failure(session, content_id, image_url, status, detail)
            result.record(status if recorded else SOURCE_CHANGED)
    await session.flush()
    return result


async def run_embedding_job(
    *,
    only_failed: bool = False,
    failure_reason: str | None = None,
    since: datetime | None = None,
    limit: int | None = None,
    batch_size: int = 50,
    concurrency: int = 8,
    session_factory: async_sessionmaker[AsyncSession] = async_session_factory,
) -> EmbedResult:
    async with session_factory() as session:
        targets = await collect_targets(
            session,
            only_failed=only_failed,
            failure_reason=failure_reason,
            since=since,
            limit=limit,
        )
    logger.info(
        "embed.job.start",
        targets=len(targets),
        only_failed=only_failed,
        failure_reason=failure_reason,
    )
    result = EmbedResult()
    if not targets:
        return result

    dl_sem = asyncio.Semaphore(max(1, concurrency))
    async with httpx.AsyncClient(headers={"user-agent": "PicTrip-embed"}) as client:
        for i in range(0, len(targets), max(1, batch_size)):
            batch = targets[i : i + max(1, batch_size)]
            async with session_factory() as session:
                await embed_spots(session, batch, client=client, dl_sem=dl_sem, result=result)
                await session.commit()
    logger.info(
        "embed.job.done",
        written=result.written,
        failed=result.failed,
        skipped=result.skipped,
        by_status=result.by_status,
    )
    return result


async def count_missing(session: AsyncSession) -> int:
    return int(
        (
            await session.execute(
                text(
                    "SELECT count(*) FROM spots s WHERE s.first_image_url IS NOT NULL "
                    "AND s.first_image_url <> '' AND NOT EXISTS "
                    "(SELECT 1 FROM spot_embeddings e WHERE e.content_id = s.content_id "
                    "AND e.image_url = s.first_image_url)"
                )
            )
        ).scalar_one()
    )
