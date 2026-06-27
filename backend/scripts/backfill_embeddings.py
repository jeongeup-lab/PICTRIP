"""Backfill CLIP embeddings for spots that have an image but no embedding row.

    uv run python -m scripts.backfill_embeddings [--limit N] [--concurrency N]
                                                 [--batch-size N] [--dry-run]

Photo-search quality is gated on embedding coverage (S04): spots without a
`spot_embeddings` row never surface as image-search matches. This walks every
spot that has `first_image_url` but no embedding, downloads the KTO image,
runs CLIP in-process, and upserts the 512-dim halfvec.

Idempotent and resumable: it only targets missing rows, so a re-run picks up
where it left off (and retries transient download/decode failures). Image bytes
are processed in memory and never persisted (only the vector is stored).
"""

from __future__ import annotations

import argparse
import asyncio

import httpx
from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.db import async_session_factory
from app.core.embedding import embedder
from app.core.logging import get_logger
from app.modules.images.models import SpotEmbedding
from app.modules.spots.models import Spot

logger = get_logger(__name__)

# CLIP is a single CPU model instance — serialise inference; parallelise only downloads.
_embed_lock = asyncio.Lock()


async def _collect_targets(limit: int | None) -> list[tuple[str, str]]:
    """(content_id, image_url) for spots with an image but no embedding row."""
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
    if limit:
        stmt = stmt.limit(limit)
    async with async_session_factory() as session:
        rows = (await session.execute(stmt)).all()
    return [(cid, url) for cid, url in rows]


async def _embed_one(
    content_id: str,
    image_url: str,
    client: httpx.AsyncClient,
    dl_sem: asyncio.Semaphore,
) -> tuple[str, str, list[float] | None, str]:
    """Download + embed one spot image. Returns (content_id, url, vector|None, status)."""
    try:
        async with dl_sem:
            resp = await client.get(image_url, timeout=20.0, follow_redirects=True)
        if resp.status_code != 200 or not resp.content:
            return (content_id, image_url, None, "download_failed")
        async with _embed_lock:
            vector = await asyncio.to_thread(embedder.embed_image, resp.content)
        return (content_id, image_url, vector, "ok")
    except Exception as exc:  # one bad image must not abort the run
        logger.warning("backfill.failed", content_id=content_id, error=str(exc))
        return (content_id, image_url, None, "error")


def _chunks(items: list[tuple[str, str]], size: int) -> list[list[tuple[str, str]]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill CLIP embeddings for image-bearing spots."
    )
    parser.add_argument("--limit", type=int, default=None, help="only the first N missing spots")
    parser.add_argument("--concurrency", type=int, default=8, help="parallel image downloads")
    parser.add_argument("--batch-size", type=int, default=100, help="spots per commit")
    parser.add_argument(
        "--dry-run", action="store_true", help="count targets, no download/embed/write"
    )
    args = parser.parse_args()

    targets = await _collect_targets(args.limit)
    print(f"missing embeddings (image-bearing spots): {len(targets)}")
    if args.dry_run or not targets:
        return

    totals: dict[str, int] = {}
    dl_sem = asyncio.Semaphore(max(1, args.concurrency))
    written = 0

    async with httpx.AsyncClient(headers={"user-agent": "PicTrip-backfill"}) as client:
        for batch in _chunks(targets, max(1, args.batch_size)):
            results = await asyncio.gather(
                *(_embed_one(cid, url, client, dl_sem) for cid, url in batch)
            )
            async with async_session_factory() as session:
                for content_id, image_url, vector, status in results:
                    totals[status] = totals.get(status, 0) + 1
                    if vector is None:
                        continue
                    stmt = (
                        pg_insert(SpotEmbedding)
                        .values(content_id=content_id, embedding=vector, image_url=image_url)
                        .on_conflict_do_update(
                            index_elements=["content_id"],
                            set_={
                                "embedding": vector,
                                "image_url": image_url,
                                "computed_at": func.now(),
                            },
                        )
                    )
                    await session.execute(stmt)
                    written += 1
                await session.commit()
            print(f"  progress: {written}/{len(targets)} embedded")

    # Report final coverage so the run is self-verifying.
    async with async_session_factory() as session:
        remaining = (
            await session.execute(
                text(
                    "SELECT count(*) FROM spots s WHERE s.first_image_url IS NOT NULL "
                    "AND s.first_image_url <> '' AND NOT EXISTS "
                    "(SELECT 1 FROM spot_embeddings e WHERE e.content_id = s.content_id)"
                )
            )
        ).scalar_one()

    print("--- backfill summary ---")
    print(f"  {'written':>16}: {written}")
    for key, val in sorted(totals.items()):
        print(f"  {key:>16}: {val}")
    print(f"  {'still_missing':>16}: {remaining}")


if __name__ == "__main__":
    asyncio.run(main())
