from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import httpx
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.db import async_session_factory
from app.core.logging import get_logger
from app.kto.client import KtoClient, KtoService
from app.modules.images.embedding_job import OK, SOURCE_CHANGED, _embed_one
from app.modules.images.models import SpotEmbeddingGallery
from app.web.errors import KtoApiUnavailable

if TYPE_CHECKING:
    from app.modules.spots.services import SpotImageRow

logger = get_logger(__name__)

MAX_GALLERY_IMAGES = 5
KTO_FAILED = "kto_failed"
NO_IMAGES = "no_images"

_kto_sem = asyncio.Semaphore(4)


@dataclass
class GalleryResult:
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
    if limit is not None:
        stmt = stmt.limit(max(0, limit))
    rows = (await session.execute(stmt)).all()
    return [(cid, url) for cid, url in rows]


def centroid(vectors: list[list[float]]) -> list[float]:
    mean = [sum(dim) / len(vectors) for dim in zip(*vectors, strict=True)]
    norm = math.sqrt(sum(v * v for v in mean)) or 1.0
    return [v / norm for v in mean]


async def _gallery_images(
    kto: KtoClient, content_id: str, first_image_url: str
) -> tuple[list[str], list[SpotImageRow]]:
    from app.modules.spots.services import parse_kto_detail_images

    async with _kto_sem:
        items = await kto.call(KtoService.KOR, "detailImage2", contentId=content_id, imageYN="Y")
    gallery = parse_kto_detail_images(items)
    urls = [first_image_url]
    for image in gallery:
        if image.origin_image_url not in urls:
            urls.append(image.origin_image_url)
        if len(urls) >= MAX_GALLERY_IMAGES:
            break
    return urls, gallery


async def _embed_gallery_one(
    content_id: str,
    first_image_url: str,
    *,
    kto: KtoClient,
    client: httpx.AsyncClient,
    dl_sem: asyncio.Semaphore,
) -> tuple[str, list[float] | None, int, str, list[SpotImageRow]]:
    try:
        urls, gallery = await _gallery_images(kto, content_id, first_image_url)
    except KtoApiUnavailable:
        return (content_id, None, 0, KTO_FAILED, [])
    outcomes = await asyncio.gather(*(_embed_one(content_id, url, client, dl_sem) for url in urls))
    vectors = [
        vector for _cid, _url, vector, status, _detail in outcomes if status == OK and vector
    ]
    if not vectors:
        return (content_id, None, 0, NO_IMAGES, gallery)
    return (content_id, centroid(vectors), len(vectors), OK, gallery)


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
    from app.modules.spots.services import replace_spot_images

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
    for content_id, vector, image_count, status, gallery in outcomes:
        if gallery:
            await replace_spot_images(session, content_id, gallery)
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
