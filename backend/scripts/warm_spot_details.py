"""Warm the spot_details cache for all home-feed / curation spots.

    uv run python -m scripts.warm_spot_details [--limit N] [--concurrency N] [--dry-run]

Idempotent: load_spot_detail skips KTO when the cached row is still fresh. Each task
uses its own session (AsyncSession is not concurrency-safe); the KTO client and Redis
pool are shared.
"""

from __future__ import annotations

import argparse
import asyncio

from redis.asyncio import Redis, from_url

from app.config import settings
from app.core.db import async_session_factory
from app.core.kto_client import KtoClient
from app.core.logging import get_logger
from app.modules.spots.services import curations as curation_svc
from app.modules.spots.services.detail import load_spot_detail

logger = get_logger(__name__)


async def _collect_ids(redis: Redis) -> list[str]:
    """Unique content_ids across published region + mood curations, order preserved."""
    seen: dict[str, None] = {}
    async with async_session_factory() as session:
        for type_ in ("region", "mood"):
            for cur in await curation_svc.list_published_curations(session, type_):
                resolved = await curation_svc.resolve_curation_spots(session, redis, cur)
                for row in resolved:
                    seen.setdefault(row.content_id, None)
    return list(seen)


async def _warm_one(
    content_id: str,
    kto: KtoClient,
    redis: Redis,
    sem: asyncio.Semaphore,
    totals: dict[str, int],
) -> None:
    async with sem, async_session_factory() as session:
        try:
            row = await load_spot_detail(session, kto, redis, content_id)
        except Exception as exc:
            totals["errors"] = totals.get("errors", 0) + 1
            logger.warning("warm.failed", content_id=content_id, error=str(exc))
            return
    totals[row.detail_status] = totals.get(row.detail_status, 0) + 1


async def main() -> None:
    parser = argparse.ArgumentParser(description="Warm spot_details cache for feed/curation spots.")
    parser.add_argument("--limit", type=int, default=None, help="only the first N ids")
    parser.add_argument("--concurrency", type=int, default=4, help="parallel KTO fetches")
    parser.add_argument("--dry-run", action="store_true", help="list ids, no KTO/DB writes")
    args = parser.parse_args()

    redis: Redis = from_url(  # type: ignore[no-untyped-call]
        str(settings.REDIS_URL),
        encoding="utf-8",
        decode_responses=True,
        max_connections=50,
    )
    try:
        ids = await _collect_ids(redis)
        if args.limit:
            ids = ids[: args.limit]
        print(f"collected {len(ids)} spot ids to warm")
        if args.dry_run:
            for cid in ids:
                print(f"  {cid}")
            return

        totals: dict[str, int] = {}
        sem = asyncio.Semaphore(max(1, args.concurrency))
        kto = KtoClient()
        try:
            await asyncio.gather(*(_warm_one(cid, kto, redis, sem, totals) for cid in ids))
        finally:
            await kto.aclose()

        print("--- warm summary ---")
        print(f"  {'total':>11}: {len(ids)}")
        for key, val in sorted(totals.items()):
            print(f"  {key:>11}: {val}")
    finally:
        await redis.aclose()


if __name__ == "__main__":
    asyncio.run(main())
