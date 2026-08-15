from __future__ import annotations

import argparse
import asyncio
from typing import cast

from redis.asyncio import Redis, from_url

from app.config import settings
from app.modules.feed.embedding_job import run_overseas_embedding_job
from app.modules.feed.services import invalidate_all_match_cache
from app.modules.images.services import (
    acquire_embedding_job_lock,
    release_embedding_job_lock,
)


async def _run_embed(redis: Redis, args: argparse.Namespace) -> dict[str, int]:
    await invalidate_all_match_cache(redis)
    try:
        return await run_overseas_embedding_job(
            limit=args.limit,
            concurrency=args.concurrency,
            batch_size=args.batch_size,
            download_pace=args.pace,
        )
    finally:
        await invalidate_all_match_cache(redis)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill CLIP embeddings for overseas spots.")
    parser.add_argument("--limit", type=int, default=None, help="only the first N missing rows")
    parser.add_argument("--concurrency", type=int, default=2, help="parallel image downloads")
    parser.add_argument("--batch-size", type=int, default=50, help="rows per commit")
    parser.add_argument(
        "--pace", type=float, default=0.3, help="seconds to hold a download slot after each fetch"
    )
    args = parser.parse_args()

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
        counters = await _run_embed(redis, args)
    finally:
        try:
            await release_embedding_job_lock(lock)
        finally:
            await redis.aclose()

    print("--- overseas embed summary ---")
    for key in ("targets", "embedded", "failed", "skipped"):
        print(f"  {key:>10}: {counters[key]}")


if __name__ == "__main__":
    asyncio.run(main())
