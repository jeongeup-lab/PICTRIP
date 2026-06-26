"""ASGI middleware: trace-id injection + request access logging + edge cache hints."""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.logging import get_logger, set_trace_id
from app.core.time import kst_now, seconds_until_kst_midnight

logger = get_logger(__name__)


class TraceIdMiddleware(BaseHTTPMiddleware):
    """Assign or propagate X-Trace-Id, expose it in response + structlog context."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        trace_id = request.headers.get("X-Trace-Id") or uuid.uuid4().hex[:16]
        set_trace_id(trace_id)
        request.state.trace_id = trace_id

        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "request.error",
                method=request.method,
                path=request.url.path,
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
            )
            raise

        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        response.headers["X-Trace-Id"] = trace_id
        logger.info(
            "request.completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        return response


class CacheControlMiddleware(BaseHTTPMiddleware):
    """Cache-Control on public 200 GETs so a CDN can serve them from the edge.

    Feed/curations expire at the next KST midnight; regions-tree after 24h.
    Requires a matching Cloudflare Cache Rule to take effect.
    """

    def __init__(self, app: ASGIApp, prefix: str) -> None:
        super().__init__(app)
        self._feed = f"{prefix}/home/feed"
        self._regions_tree = f"{prefix}/map/regions-tree"
        self._curations_prefix = f"{prefix}/curations/"

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        if request.method != "GET" or response.status_code != 200:
            return response

        path = request.url.path
        if path == self._feed or path.startswith(self._curations_prefix):
            ttl = seconds_until_kst_midnight(kst_now())
            response.headers["Cache-Control"] = f"public, s-maxage={ttl}"
        elif path == self._regions_tree:
            response.headers["Cache-Control"] = "public, s-maxage=86400"
        return response
