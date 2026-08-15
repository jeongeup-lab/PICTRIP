from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Request
from redis.asyncio import Redis

from app.core.logging import get_logger
from app.core.redis import RedisDep
from app.web.errors import RateLimited

logger = get_logger(__name__)


def _client_ip(request: Request) -> str:
    cf = request.headers.get("cf-connecting-ip")
    if cf:
        return cf.strip()
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def _enforce(redis: Redis, *, key: str, limit: int, window_seconds: int) -> None:
    try:
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, window_seconds)
    except Exception:
        logger.warning("rate_limit_unavailable_fail_open", key=key)
        return
    if count > limit:
        raise RateLimited()


def rate_limit(
    *, bucket: str, limit: int, window_seconds: int
) -> Callable[[Request, Redis], Awaitable[None]]:

    async def _dep(request: Request, redis: RedisDep) -> None:
        await _enforce(
            redis,
            key=f"rl:{bucket}:{_client_ip(request)}",
            limit=limit,
            window_seconds=window_seconds,
        )

    return _dep
