from __future__ import annotations

import argparse
import asyncio
from typing import cast

from redis.asyncio import Redis, from_url

from app.config import settings
from app.core.db import async_session_factory
from app.modules.feed.services import recompute_all_matches
from app.modules.images.embedding_job import (
    EmbedResult,
    collect_targets,
    count_missing,
    run_embedding_job,
)
from app.modules.images.services import (
    acquire_embedding_job_lock,
    release_embedding_job_lock,
)


async def _run_backfill(redis: Redis, args: argparse.Namespace) -> EmbedResult:
    try:
        return await run_embedding_job(
            only_failed=args.only_failed,
            failure_reason=args.failure_reason,
            limit=args.limit,
            batch_size=args.batch_size,
            concurrency=args.concurrency,
        )
    finally:
        await recompute_all_matches()


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill CLIP embeddings for image-bearing spots."
    )
    parser.add_argument("--limit", type=int, default=None, help="only the first N missing spots")
    parser.add_argument("--concurrency", type=int, default=8, help="parallel image downloads")
    parser.add_argument("--batch-size", type=int, default=100, help="spots per commit")
    parser.add_argument(
        "--only-failed", action="store_true", help="retry only previously-failed spots"
    )
    parser.add_argument(
        "--failure-reason", type=str, default=None, help="retry only this failure reason"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="count targets, no download/embed/write"
    )
    args = parser.parse_args()

    if args.dry_run:
        async with async_session_factory() as session:
            targets = await collect_targets(
                session,
                only_failed=args.only_failed,
                failure_reason=args.failure_reason,
                limit=args.limit,
            )
        print(f"missing embeddings (image-bearing spots): {len(targets)}")
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
        remaining = await count_missing(session)

    print("--- backfill summary ---")
    print(f"  {'written':>16}: {result.written}")
    for key, val in sorted(result.by_status.items()):
        print(f"  {key:>16}: {val}")
    print(f"  {'still_missing':>16}: {remaining}")


if __name__ == "__main__":
    asyncio.run(main())
