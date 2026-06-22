"""Async Redis: one lifespan-managed pool exposed via get_redis / RedisDep.

The denylist auth model + all application caches store text values, so the pool
runs with ``decode_responses=True``. The old binary session payloads are gone.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI
from redis.asyncio import Redis, from_url

from app.config import settings

_redis: Redis | None = None


def get_redis() -> Redis:
    """FastAPI dependency. Returns the lifespan-installed Redis client."""
    if _redis is None:
        raise RuntimeError("Redis client not initialized. Did the lifespan run?")
    return _redis


RedisDep = Annotated[Redis, Depends(get_redis)]


@asynccontextmanager
async def redis_lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Initialise and tear down the single Redis pool."""
    global _redis
    _redis = from_url(  # type: ignore[no-untyped-call]
        str(settings.REDIS_URL),
        encoding="utf-8",
        decode_responses=True,
        max_connections=50,
    )
    try:
        yield
    finally:
        await _redis.aclose()
        _redis = None
