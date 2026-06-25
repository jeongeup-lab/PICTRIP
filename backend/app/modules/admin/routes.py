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
from app.core.redis import RedisDep
from app.core.schemas import ok
from app.modules.admin import services
from app.modules.admin.schemas import CurationUpdate, SpotsUpdate
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


@router.get("/curation")
async def admin_curation(_: AdminAuth) -> FileResponse:
    """홈 큐레이션 편집기 (curation.html; ADM-017)."""
    return _page("curation.html")


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


# --- Curation editor (A01 §7 / ADM-012~015) — admin's scoped write surface ----
@router.get("/api/curations")
async def api_curations_list(_: AdminAuth, db: DbSession) -> dict[str, Any]:
    """CurationList — heroes/rails/editorial grouped, each by position (ADM-012)."""
    return ok(await services.list_curations(db))


@router.get("/api/curations/{curation_id}")
async def api_curation_detail(_: AdminAuth, db: DbSession, curation_id: int) -> dict[str, Any]:
    """CurationDetail — copy/cover/handpicks; 404 ADMIN_CURATION_NOT_FOUND (ADM-012)."""
    return ok(await services.get_curation_detail(db, curation_id))


@router.put("/api/curations/{curation_id}")
async def api_curation_update(
    _: AdminAuth, db: DbSession, redis: RedisDep, curation_id: int, body: CurationUpdate
) -> dict[str, Any]:
    """Edit copy/cover/publish/position; on-publish cache DEL + audit (ADM-013/016)."""
    return ok(await services.update_curation(db, redis, curation_id, body))


@router.put("/api/curations/{curation_id}/spots")
async def api_curation_spots(
    _: AdminAuth, db: DbSession, redis: RedisDep, curation_id: int, body: SpotsUpdate
) -> dict[str, Any]:
    """Replace handpicks (≤8, ordered); cache DEL + audit (ADM-014/016)."""
    return ok(await services.set_curation_spots(db, redis, curation_id, body))


@router.get("/api/spots/search")
async def api_spots_search(
    _: AdminAuth,
    db: DbSession,
    q: str = Query(..., min_length=1),
    region: str | None = Query(None),
) -> dict[str, Any]:
    """Admin-only spot picker — trgm ILIKE title/addr1, show_flag=1, ≤20 (ADM-015)."""
    return ok(await services.search_spots(db, q, region, limit=20))
