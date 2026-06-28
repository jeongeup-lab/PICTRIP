"""Backfill CLIP embeddings for spots that have an image but no embedding row.

    uv run python -m scripts.backfill_embeddings [--limit N] [--concurrency N]
                                                 [--batch-size N] [--dry-run]
                                                 [--only-failed]

Photo-search quality is gated on embedding coverage (S04): spots without a
`spot_embeddings` row never surface as image-search matches. This walks every
spot that has `first_image_url` but no embedding, downloads the KTO image,
runs CLIP in-process, and upserts the 512-dim halfvec.

The actual work lives in ``app.modules.images.embedding_job`` (shared with the
admin console's re-embed button). Failures are recorded in ``embedding_failures``
so a missing embedding is distinguishable as pending vs. broken.

Idempotent and resumable: it only targets missing rows, so a re-run picks up
where it left off (and retries transient download/decode failures). Image bytes
are processed in memory and never persisted (only the vector is stored).
"""

from __future__ import annotations

import argparse
import asyncio

from app.core.db import async_session_factory
from app.modules.images.embedding_job import collect_targets, count_missing, run_embedding_job


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
        "--dry-run", action="store_true", help="count targets, no download/embed/write"
    )
    args = parser.parse_args()

    if args.dry_run:
        async with async_session_factory() as session:
            targets = await collect_targets(session, only_failed=args.only_failed, limit=args.limit)
        print(f"missing embeddings (image-bearing spots): {len(targets)}")
        return

    result = await run_embedding_job(
        only_failed=args.only_failed,
        limit=args.limit,
        batch_size=args.batch_size,
        concurrency=args.concurrency,
    )

    async with async_session_factory() as session:
        remaining = await count_missing(session)

    print("--- backfill summary ---")
    print(f"  {'written':>16}: {result.written}")
    for key, val in sorted(result.by_status.items()):
        print(f"  {key:>16}: {val}")
    print(f"  {'still_missing':>16}: {remaining}")


if __name__ == "__main__":
    asyncio.run(main())
