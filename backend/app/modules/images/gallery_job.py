"""Gallery (multi-image) CLIP embedding job — builds ``spot_embeddings_gallery``
centroid rows for attraction-bucket spots, shared by the CLI backfill
(``scripts.backfill_gallery_embeddings``).

Each target spot gets one 512-dim centroid: the L2-normalised mean of up to
``MAX_GALLERY_IMAGES`` per-image CLIP vectors (firstimage + KTO ``detailImage2``
originals). Averaging several views of the same place smooths the
single-representative-photo lottery that dominates overseas→domestic matching
noise (S13 §5.2).

Resumable by construction: a spot is a target only while it lacks a gallery row
anchored to its *current* ``first_image_url``, and a KTO/API failure writes no
row, so a re-run picks up exactly the unfinished spots. Image bytes are
processed in memory and never persisted (only the vector is stored) — per the
KTO image prohibition.
"""

from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass, field

import httpx
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.db import async_session_factory
from app.core.exceptions import KtoApiUnavailable
from app.core.kto_client import KtoClient, KtoService
from app.core.logging import get_logger
from app.modules.images.embedding_job import OK, SOURCE_CHANGED, _embed_one
from app.modules.images.models import SpotEmbeddingGallery

logger = get_logger(__name__)

MAX_GALLERY_IMAGES = 5
KTO_FAILED = "kto_failed"
NO_IMAGES = "no_images"

_kto_sem = asyncio.Semaphore(4)


@dataclass
class GalleryResult:
    """Aggregate counts for one gallery embed run."""

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


async def collect_gallery_targets(
    session: AsyncSession, *, limit: int | None = None
) -> list[tuple[str, str]]:
    """(content_id, first_image_url) for attraction spots without a gallery row
    anchored to their current image. Stale rows (image changed) count as missing.
    """
    from app.modules.spots.services import attraction_image_spots_stmt

    spots = attraction_image_spots_stmt().subquery()
    has_current_gallery = select(SpotEmbeddingGallery.content_id).where(
        SpotEmbeddingGallery.content_id == spots.c.content_id,
        SpotEmbeddingGallery.image_url == spots.c.first_image_url,
    )
    stmt = (
        select(spots.c.content_id, spots.c.first_image_url)
        .where(~has_current_gallery.exists())
        .order_by(spots.c.content_id)
    )
    if limit:
        stmt = stmt.limit(limit)
    rows = (await session.execute(stmt)).all()
    return [(cid, url) for cid, url in rows]


def centroid(vectors: list[list[float]]) -> list[float]:
    mean = [sum(dim) / len(vectors) for dim in zip(*vectors, strict=True)]
    norm = math.sqrt(sum(v * v for v in mean)) or 1.0
    return [v / norm for v in mean]


async def _gallery_image_urls(kto: KtoClient, content_id: str, first_image_url: str) -> list[str]:
    async with _kto_sem:
        items = await kto.call(KtoService.KOR, "detailImage2", contentId=content_id, imageYN="Y")
    urls = [first_image_url]
    for item in items:
        origin = item.get("originimgurl")
        if isinstance(origin, str) and origin and origin not in urls:
            urls.append(origin)
        if len(urls) >= MAX_GALLERY_IMAGES:
            break
    return urls


async def _embed_gallery_one(
    content_id: str,
    first_image_url: str,
    *,
    kto: KtoClient,
    client: httpx.AsyncClient,
    dl_sem: asyncio.Semaphore,
) -> tuple[str, list[float] | None, int, str]:
    """Returns (content_id, centroid|None, image_count, status)."""
    try:
        urls = await _gallery_image_urls(kto, content_id, first_image_url)
    except KtoApiUnavailable:
        return (content_id, None, 0, KTO_FAILED)
    outcomes = await asyncio.gather(*(_embed_one(content_id, url, client, dl_sem) for url in urls))
    vectors = [
        vector for _cid, _url, vector, status, _detail in outcomes if status == OK and vector
    ]
    if not vectors:
        return (content_id, None, 0, NO_IMAGES)
    return (content_id, centroid(vectors), len(vectors), OK)


async def _record_gallery(
    session: AsyncSession,
    content_id: str,
    image_url: str,
    vector: list[float],
    image_count: int,
) -> bool:
    from app.modules.spots.services import lock_current_spot_image

    if not await lock_current_spot_image(session, content_id, image_url):
        return False
    stmt = (
        pg_insert(SpotEmbeddingGallery)
        .values(
            content_id=content_id,
            embedding=vector,
            image_url=image_url,
            image_count=image_count,
        )
        .on_conflict_do_update(
            index_elements=["content_id"],
            set_={
                "embedding": vector,
                "image_url": image_url,
                "image_count": image_count,
                "computed_at": func.now(),
            },
        )
    )
    await session.execute(stmt)
    return True


async def embed_gallery_spots(
    session: AsyncSession,
    targets: list[tuple[str, str]],
    *,
    kto: KtoClient,
    client: httpx.AsyncClient,
    dl_sem: asyncio.Semaphore,
    result: GalleryResult | None = None,
) -> GalleryResult:
    """Embed one batch of (content_id, first_image_url) targets using ``session``.
    Failures write no row (the next run retries them). Flushes but does NOT
    commit — the caller owns the transaction boundary.
    """
    result = result or GalleryResult()
    if not targets:
        return result

    outcomes = await asyncio.gather(
        *(
            _embed_gallery_one(cid, url, kto=kto, client=client, dl_sem=dl_sem)
            for cid, url in targets
        )
    )
    by_id = dict(targets)
    for content_id, vector, image_count, status in outcomes:
        if status == OK and vector is not None:
            written = await _record_gallery(
                session, content_id, by_id[content_id], vector, image_count
            )
            result.record(OK if written else SOURCE_CHANGED)
        else:
            result.record(status)
    await session.flush()
    return result


async def run_gallery_embedding_job(
    *,
    limit: int | None = None,
    batch_size: int = 50,
    concurrency: int = 8,
    session_factory: async_sessionmaker[AsyncSession] = async_session_factory,
) -> GalleryResult:
    """Orchestrate a full gallery embed run: collect targets, then embed
    batch-by-batch with its own sessions + HTTP/KTO clients. Commits per batch.
    """
    async with session_factory() as session:
        targets = await collect_gallery_targets(session, limit=limit)
    logger.info("gallery_embed.job.start", targets=len(targets))
    result = GalleryResult()
    if not targets:
        return result

    dl_sem = asyncio.Semaphore(max(1, concurrency))
    kto = KtoClient()
    try:
        async with httpx.AsyncClient(headers={"user-agent": "PicTrip-embed"}) as client:
            for i in range(0, len(targets), max(1, batch_size)):
                batch = targets[i : i + max(1, batch_size)]
                async with session_factory() as session:
                    await embed_gallery_spots(
                        session, batch, kto=kto, client=client, dl_sem=dl_sem, result=result
                    )
                    await session.commit()
    finally:
        await kto.aclose()
    logger.info(
        "gallery_embed.job.done",
        written=result.written,
        failed=result.failed,
        skipped=result.skipped,
        by_status=result.by_status,
    )
    return result
