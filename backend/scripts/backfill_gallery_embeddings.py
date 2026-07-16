"""Backfill gallery (multi-image centroid) embeddings for attraction spots.

    uv run python -m scripts.backfill_gallery_embeddings [--limit N] [--concurrency N]
                                                         [--batch-size N] [--dry-run]

Overseas→domestic matching quality is capped by the single-representative-photo
lottery: both sides embed exactly one image, so whatever that photo happens to
show dominates the match. This walks every attraction-bucket spot with an image
but no fresh ``spot_embeddings_gallery`` row, fetches its KTO ``detailImage2``
gallery, embeds up to 5 photos, and upserts the L2-normalised centroid.

The actual work lives in ``app.modules.images.gallery_job``. Failures write no
row, so a re-run is resumable (KTO quota exhaustion mid-run is safe). Shares the
Redis embedding lock with the single-image job — CLIP is one CPU model, only one
embed job of any kind runs at a time. Image bytes are processed in memory and
never persisted (only the vector is stored).
"""

from __future__ import annotations

import argparse
import asyncio
from typing import cast

from redis.asyncio import Redis, from_url

from app.config import settings
from app.core.db import async_session_factory
from app.modules.feed.services import invalidate_all_match_cache
from app.modules.images.gallery_job import (
    GalleryResult,
    collect_gallery_targets,
    run_gallery_embedding_job,
)
from app.modules.images.services import (
    acquire_embedding_job_lock,
    release_embedding_job_lock,
)


async def _run_backfill(redis: Redis, args: argparse.Namespace) -> GalleryResult:
    try:
        return await run_gallery_embedding_job(
            limit=args.limit,
            batch_size=args.batch_size,
            concurrency=args.concurrency,
        )
    finally:
        await invalidate_all_match_cache(redis)


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill gallery centroid embeddings for attraction spots."
    )
    parser.add_argument("--limit", type=int, default=None, help="only the first N missing spots")
    parser.add_argument("--concurrency", type=int, default=8, help="parallel image downloads")
    parser.add_argument("--batch-size", type=int, default=50, help="spots per commit")
    parser.add_argument(
        "--dry-run", action="store_true", help="count targets, no KTO/download/embed/write"
    )
    args = parser.parse_args()

    if args.dry_run:
        async with async_session_factory() as session:
            targets = await collect_gallery_targets(session, limit=args.limit)
        print(f"missing gallery embeddings (attraction spots): {len(targets)}")
        return

    redis = cast(
        Redis,
        from_url(
            str(settings.REDIS_URL),
            encoding="utf-8",
            decode_responses=True,
            max_connections=10,
        ),
    )
    lock = await acquire_embedding_job_lock(redis)
    if lock is None:
        await redis.aclose()
        raise RuntimeError("embedding job is already running")
    try:
        result = await _run_backfill(redis, args)
    finally:
        try:
            await release_embedding_job_lock(lock)
        finally:
            await redis.aclose()

    async with async_session_factory() as session:
        remaining = len(await collect_gallery_targets(session))

    print("--- gallery backfill summary ---")
    print(f"  {'written':>16}: {result.written}")
    for key, val in sorted(result.by_status.items()):
        print(f"  {key:>16}: {val}")
    print(f"  {'still_missing':>16}: {remaining}")


if __name__ == "__main__":
    asyncio.run(main())
