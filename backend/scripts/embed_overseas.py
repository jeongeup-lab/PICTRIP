"""Backfill CLIP embeddings for overseas spots that have no embedding yet.

    uv run python -m scripts.embed_overseas [--limit N] [--concurrency N]
                                            [--batch-size N]

Runs on CT112 after the pipeline loads the Wikidata/Commons overseas rows: it
walks every ``overseas_spots`` row whose ``embedding`` is NULL, downloads the
Commons image (Wikimedia 403s odd user-agents, so a real UA is sent), runs CLIP
in-process, and writes the 512-dim halfvec.

Idempotent and resumable: only NULL rows are targeted, so a re-run picks up where
it left off and retries transient download/decode failures. There is no failure
table for overseas rows — failures are counted + logged, and re-running covers
them. Image bytes are processed in memory and never persisted (only the vector).
"""

from __future__ import annotations

import argparse
import asyncio

from app.modules.feed.embedding_job import run_overseas_embedding_job


async def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill CLIP embeddings for overseas spots.")
    parser.add_argument("--limit", type=int, default=None, help="only the first N missing rows")
    parser.add_argument("--concurrency", type=int, default=2, help="parallel image downloads")
    parser.add_argument("--batch-size", type=int, default=50, help="rows per commit")
    parser.add_argument(
        "--pace", type=float, default=0.3, help="seconds to hold a download slot after each fetch"
    )
    args = parser.parse_args()

    counters = await run_overseas_embedding_job(
        limit=args.limit,
        concurrency=args.concurrency,
        batch_size=args.batch_size,
        download_pace=args.pace,
    )

    print("--- overseas embed summary ---")
    for key in ("targets", "embedded", "failed"):
        print(f"  {key:>10}: {counters[key]}")


if __name__ == "__main__":
    asyncio.run(main())
