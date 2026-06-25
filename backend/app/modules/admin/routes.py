"""admin routes — /admin (HTML) + /admin/api/* (JSON).

Serves the three static mockup pages (수집 현황 · 수집 이력 · 서비스 헬스) and the
Phase 1 read-only JSON API (A01 §3). Every route is guarded by HTTP Basic auth
(``AdminAuth``). Routes do HTTP I/O only — aggregation lives in ``services``.
The JSON API is ``/admin/api/*`` (outside ``/v1``; A01 §1.2) and wrapped in the
standard JSend envelope via ``ok()``.
"""

from __future__ import annotations

from datetime import date as date_type
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse

from app.core.db import DbSession
from app.core.schemas import ok
from app.modules.admin import services
from app.modules.admin.security import AdminAuth

_STATIC_DIR = Path(__file__).parent / "static"

router = APIRouter(tags=["ADM · admin console"], include_in_schema=False)

# Security headers for the served admin HTML. The console only loads same-origin
# CSS/JS; img-src allows https: because the curation/health views may render KTO
# image URLs, and style-src allows 'unsafe-inline' because the mockups carry
# inline style attributes. frame-ancestors/X-Frame-Options block clickjacking.
_HTML_SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; "
        "object-src 'none'; frame-ancestors 'none'"
    ),
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
}


def _page(name: str) -> FileResponse:
    return FileResponse(_STATIC_DIR / name, media_type="text/html", headers=_HTML_SECURITY_HEADERS)


# --- Static HTML pages --------------------------------------------------------
@router.get("")
@router.get("/")
async def admin_index(_: AdminAuth) -> FileResponse:
    """수집 현황 (index.html). Served at both /admin and /admin/ (trailing slash)."""
    return _page("index.html")


@router.get("/history")
async def admin_history(_: AdminAuth) -> FileResponse:
    """수집 이력 (history.html)."""
    return _page("history.html")


@router.get("/health")
async def admin_health(_: AdminAuth) -> FileResponse:
    """서비스 헬스 (health.html)."""
    return _page("health.html")


# --- JSON API (A01 §3) --------------------------------------------------------
@router.get("/api/collection")
async def api_collection(_: AdminAuth, db: DbSession) -> dict[str, Any]:
    """CollectionStatus — totalSpots + latest run + next schedule (A01 §2.1)."""
    return ok(await services.get_collection_status(db))


@router.get("/api/history")
async def api_history(
    _: AdminAuth, db: DbSession, days: int = Query(7, ge=1, le=90)
) -> dict[str, Any]:
    """HistoryList — per-day success/error/running rollup over N days (A01 §2.2)."""
    return ok(await services.get_history(db, days))


@router.get("/api/history/{run_date}")
async def api_history_detail(_: AdminAuth, db: DbSession, run_date: date_type) -> dict[str, Any]:
    """HistoryDetail — runs for one day; 404 ADMIN_HISTORY_NOT_FOUND if none."""
    return ok(await services.get_history_detail(db, run_date))


@router.get("/api/health")
async def api_health(_: AdminAuth, db: DbSession) -> dict[str, Any]:
    """Health — api/db/tunnel/users component status (A01 §2.3)."""
    return ok(await services.get_health(db))
