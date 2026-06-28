"""CLIP embedding job — the single code path for turning image-bearing spots into
``spot_embeddings`` rows, shared by the CLI backfill (``scripts.backfill_embeddings``)
and the admin console's "재임베딩" button.

Collection and embedding are separate steps (a spot can exist for hours before its
image is embedded). This module:

- ``collect_targets`` — finds (content_id, image_url) pairs that still need an
  embedding (optionally only previously-failed ones, optionally scoped to a sync
  window).
- ``embed_spots`` — downloads + embeds a batch against a *passed* session,
  recording successes in ``spot_embeddings`` and failures in ``embedding_failures``
  (so a missing embedding is distinguishable as pending vs. broken).
- ``run_embedding_job`` — the orchestrator that owns its own sessions + HTTP
  client, used by the background trigger and the CLI.

Image bytes are processed in memory and never persisted (only the vector is
stored) — per the KTO image prohibition.
"""

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

# CLIP is a single CPU model instance — serialise inference; parallelise only downloads.
_embed_lock = asyncio.Lock()

# Status codes returned by _embed_one / used as embedding_failures.reason.
OK = "ok"
DOWNLOAD_FAILED = "download_failed"
CLIP_ERROR = "clip_error"


@dataclass
class EmbedResult:
    """Aggregate counts for one embed run."""

    written: int = 0
    failed: int = 0
    by_status: dict[str, int] = field(default_factory=dict)

    def record(self, status: str) -> None:
        self.by_status[status] = self.by_status.get(status, 0) + 1
        if status == OK:
            self.written += 1
        else:
            self.failed += 1


async def collect_targets(
    session: AsyncSession,
    *,
    only_failed: bool = False,
    since: datetime | None = None,
    limit: int | None = None,
) -> list[tuple[str, str]]:
    """(content_id, image_url) for image-bearing spots that have no embedding row.

    ``only_failed`` restricts to spots already recorded in ``embedding_failures``
    (the admin "retry failures" scope). ``since`` restricts to spots synced at or
    after that time (the "this collection" scope). ``limit`` caps the batch so the
    serving process is never pinned by a huge backlog.
    """
    # Imported lazily: a module-level spots.models import would re-enter
    # images.services (which re-exports this module) → circular import.
    from app.modules.spots.models import Spot

    has_embedding = select(SpotEmbedding.content_id).where(
        SpotEmbedding.content_id == Spot.content_id
    )
    stmt = (
        select(Spot.content_id, Spot.first_image_url)
        .where(Spot.first_image_url.is_not(None))
        .where(Spot.first_image_url != "")
        .where(~has_embedding.exists())
        .order_by(Spot.content_id)
    )
    if only_failed:
        has_failure = select(EmbeddingFailure.content_id).where(
            EmbeddingFailure.content_id == Spot.content_id
        )
        stmt = stmt.where(has_failure.exists())
    if since is not None:
        stmt = stmt.where(Spot.synced_at >= since)
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
    """Download + embed one spot image.

    Returns (content_id, url, vector|None, status, error_detail). ``status`` is one
    of OK / DOWNLOAD_FAILED / CLIP_ERROR; ``error_detail`` is a short message for
    the failure record (None on success).
    """
    try:
        async with dl_sem:
            resp = await client.get(image_url, timeout=20.0, follow_redirects=True)
        if resp.status_code != 200 or not resp.content:
            return (content_id, image_url, None, DOWNLOAD_FAILED, f"HTTP {resp.status_code}")
        async with _embed_lock:
            vector = await asyncio.to_thread(embedder.embed_image, resp.content)
        return (content_id, image_url, vector, OK, None)
    except Exception as exc:  # one bad image must not abort the run
        logger.warning("embed.failed", content_id=content_id, error=str(exc))
        return (content_id, image_url, None, CLIP_ERROR, str(exc)[:500])


async def _record_success(
    session: AsyncSession, content_id: str, image_url: str, vector: list[float]
) -> None:
    stmt = (
        pg_insert(SpotEmbedding)
        .values(content_id=content_id, embedding=vector, image_url=image_url)
        .on_conflict_do_update(
            index_elements=["content_id"],
            set_={"embedding": vector, "image_url": image_url, "computed_at": func.now()},
        )
    )
    await session.execute(stmt)
    # Clear any prior failure record — this spot is now embedded.
    await session.execute(delete(EmbeddingFailure).where(EmbeddingFailure.content_id == content_id))


async def _record_failure(
    session: AsyncSession, content_id: str, reason: str, detail: str | None
) -> None:
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


async def embed_spots(
    session: AsyncSession,
    targets: list[tuple[str, str]],
    *,
    client: httpx.AsyncClient,
    dl_sem: asyncio.Semaphore,
    result: EmbedResult | None = None,
) -> EmbedResult:
    """Embed one batch of (content_id, image_url) targets using ``session``.

    Writes ``spot_embeddings`` for successes and ``embedding_failures`` for
    failures (clearing the failure row when a previously-failed spot now succeeds).
    Flushes but does NOT commit — the caller owns the transaction boundary.
    """
    result = result or EmbedResult()
    if not targets:
        return result

    outcomes = await asyncio.gather(*(_embed_one(cid, url, client, dl_sem) for cid, url in targets))
    for content_id, image_url, vector, status, detail in outcomes:
        result.record(status)
        if status == OK and vector is not None:
            await _record_success(session, content_id, image_url, vector)
        else:
            await _record_failure(session, content_id, status, detail)
    await session.flush()
    return result


async def run_embedding_job(
    *,
    only_failed: bool = False,
    since: datetime | None = None,
    limit: int | None = None,
    batch_size: int = 50,
    concurrency: int = 8,
    session_factory: async_sessionmaker[AsyncSession] = async_session_factory,
) -> EmbedResult:
    """Orchestrate a full embed run: collect targets, then embed batch-by-batch
    with its own sessions + HTTP client (so it is safe to fire from a FastAPI
    BackgroundTask after the request session has closed). Commits per batch.
    """
    async with session_factory() as session:
        targets = await collect_targets(session, only_failed=only_failed, since=since, limit=limit)
    logger.info("embed.job.start", targets=len(targets), only_failed=only_failed)
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
        "embed.job.done", written=result.written, failed=result.failed, by_status=result.by_status
    )
    return result


async def count_missing(session: AsyncSession) -> int:
    """Image-bearing spots with no embedding (the all-time backlog)."""
    return int(
        (
            await session.execute(
                text(
                    "SELECT count(*) FROM spots s WHERE s.first_image_url IS NOT NULL "
                    "AND s.first_image_url <> '' AND NOT EXISTS "
                    "(SELECT 1 FROM spot_embeddings e WHERE e.content_id = s.content_id)"
                )
            )
        ).scalar_one()
    )
