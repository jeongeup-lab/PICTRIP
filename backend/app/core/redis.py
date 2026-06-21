"""Async Redis client + FastAPI lifespan + DI dependency.

Two pools are exposed:
- ``redis_cache``  for application caches (spot_details, crowd, etc.)
- ``_redis``       managed session client exposed via ``get_redis`` / ``RedisDep``
                   and initialised/torn-down by the FastAPI lifespan.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI
from redis.asyncio import Redis, from_url

from app.config import settings

# ---------------------------------------------------------------------------
# Module-level cache pool (pre-existing singleton, used by SPT/SYS caches)
# ---------------------------------------------------------------------------

redis_cache: Redis = from_url(  # type: ignore[no-untyped-call]
    str(settings.REDIS_URL),
    encoding="utf-8",
    decode_responses=True,
    max_connections=50,
)


async def close_redis() -> None:
    """Close the shared cache pool. Called from the FastAPI lifespan."""
    await redis_cache.aclose()


# ---------------------------------------------------------------------------
# Lifespan-managed DI client
# ---------------------------------------------------------------------------

_redis: Redis | None = None


def get_redis() -> Redis:
    """FastAPI dependency. Returns the lifespan-installed Redis client."""
    if _redis is None:
        raise RuntimeError("Redis client not initialized. Did the lifespan run?")
    return _redis


RedisDep = Annotated[Redis, Depends(get_redis)]


@asynccontextmanager
async def redis_lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Async context manager that initialises and tears down ``_redis``."""
    global _redis
    _redis = from_url(str(settings.REDIS_URL), decode_responses=False)  # type: ignore[no-untyped-call]
    try:
        yield
    finally:
        await _redis.aclose()
        _redis = None
