"""Warm the festa·pets·snap channel caches ahead of any visitor.

    uv run python -m scripts.warm_channels

Populates each channel's Redis entry with today's date so the home request path
serves a cache hit instead of blocking on a live KTO fetch. Run on a daily cron
and once right after deploy. Fail-soft per channel — a single KTO outage does not
abort the others.
"""

from __future__ import annotations

import asyncio

from redis.asyncio import Redis, from_url

from app.config import settings
from app.core.kto_client import KtoClient
from app.core.logging import get_logger
from app.modules.feed.services.kto_channels import warm_all_channels

logger = get_logger(__name__)


async def main() -> None:
    redis: Redis = from_url(  # type: ignore[no-untyped-call]
        str(settings.REDIS_URL),
        encoding="utf-8",
        decode_responses=True,
        max_connections=10,
    )
    kto = KtoClient()
    try:
        outcomes = await warm_all_channels(redis, kto)
    finally:
        await kto.aclose()
        await redis.aclose()

    print("--- channel warm summary ---")
    for key, ok in outcomes.items():
        print(f"  {key:>6}: {'ok' if ok else 'FAILED'}")


if __name__ == "__main__":
    asyncio.run(main())
