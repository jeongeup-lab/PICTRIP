"""FastAPI application entrypoint.

Wires lifespan (DB pool warm-up, Sentry init, KTO client), middleware (trace-id,
CORS, trusted hosts), error handlers, and all 6 domain routers under /v1.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sentry_sdk.integrations.fastapi import FastApiIntegration
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.config import settings
from app.core.error_handlers import register_error_handlers
from app.core.kto_client import KtoClient
from app.core.logging import configure_logging, get_logger
from app.core.middleware import TraceIdMiddleware
from app.core.redis import redis_lifespan
from app.core.schemas import ok
from app.core.version import API_VERSION
from app.modules.admin import router as admin_router
from app.modules.images import router as images_router
from app.modules.map import router as map_router
from app.modules.spots import router as spots_router
from app.modules.system import router as system_router
from app.modules.taste import router as taste_router
from app.modules.users import router as users_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    logger = get_logger(__name__)

    if settings.SENTRY_DSN:
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.ENVIRONMENT,
            traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
            profiles_sample_rate=settings.SENTRY_PROFILES_SAMPLE_RATE,
            integrations=[FastApiIntegration()],
        )

    app.state.kto = KtoClient()
    logger.info("app.startup", environment=settings.ENVIRONMENT)

    async with redis_lifespan(app):
        try:
            yield
        finally:
            await app.state.kto.aclose()
            logger.info("app.shutdown")


def create_app() -> FastAPI:
    app = FastAPI(
        title="PicTrip API",
        version=API_VERSION,
        description="Image-based Korea tourism recommendation service backend.",
        openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
        docs_url=f"{settings.API_V1_PREFIX}/docs",
        redoc_url=f"{settings.API_V1_PREFIX}/redoc",
        lifespan=lifespan,
    )

    # --- Middleware (order: outermost first) ---
    if settings.TRUSTED_HOSTS and settings.TRUSTED_HOSTS != ["*"]:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.TRUSTED_HOSTS)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS or ["*"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Trace-Id"],
        expose_headers=["X-Trace-Id"],
        max_age=86400,
    )
    app.add_middleware(TraceIdMiddleware)

    # --- Error handlers ---
    register_error_handlers(app)

    # --- Liveness (outside /v1 — used by ALB) ---
    @app.get("/health", include_in_schema=False)
    async def health() -> dict[str, Any]:
        return ok({"status": "ok"})

    # --- Admin console (outside /v1 — internal ops surface; A01 §1.2) ---
    app.include_router(admin_router, prefix="/admin")
    admin_assets = Path(__file__).parent / "modules" / "admin" / "static" / "assets"
    # PUBLIC/unauthenticated mount: must contain ONLY non-sensitive CSS/JS
    # (no data, no secrets, no source maps) — it is served without the AdminAuth gate.
    app.mount(
        "/admin/assets",
        StaticFiles(directory=admin_assets),
        name="admin-assets",
    )

    # --- Routers under /v1 ---
    prefix = settings.API_V1_PREFIX
    app.include_router(users_router, prefix=prefix)
    app.include_router(taste_router, prefix=prefix)
    app.include_router(spots_router, prefix=prefix)
    app.include_router(images_router, prefix=prefix)
    app.include_router(map_router, prefix=prefix)
    app.include_router(system_router, prefix=prefix)

    return app


app = create_app()
