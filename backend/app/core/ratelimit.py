"""Per-IP fixed-window rate limiting on Redis.

Fail-open (S08): a Redis blip must never block authentication, matching the
denylist model in ``app.core.auth``. Only the over-limit decision raises
``RateLimited``; any Redis error degrades to "allow" and logs a warning.

Used as a route dependency, e.g.::

    @router.post("/auth/email/login", dependencies=[
        Depends(rate_limit(bucket="email_login", limit=10, window_seconds=60)),
    ])
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Request
from redis.asyncio import Redis

from app.core.exceptions import RateLimited
from app.core.logging import get_logger
from app.core.redis import RedisDep

logger = get_logger(__name__)


def _client_ip(request: Request) -> str:
    """Resolve the caller IP behind the Cloudflare tunnel.

    The CF edge sets ``CF-Connecting-IP``; fall back to the first
    ``X-Forwarded-For`` hop, then the socket peer. A spoofed header only lets an
    attacker spread their own quota, never bypass another client's bucket."""
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
    except Exception:  # Redis blip -> fail-open (S08); alarm so it isn't silent
        logger.warning("rate_limit_unavailable_fail_open", key=key)
        return
    if count > limit:
        raise RateLimited()


def rate_limit(
    *, bucket: str, limit: int, window_seconds: int
) -> Callable[[Request, Redis], Awaitable[None]]:
    """Build a FastAPI dependency throttling ``limit`` requests / window per IP."""

    async def _dep(request: Request, redis: RedisDep) -> None:
        await _enforce(
            redis,
            key=f"rl:{bucket}:{_client_ip(request)}",
            limit=limit,
            window_seconds=window_seconds,
        )

    return _dep
