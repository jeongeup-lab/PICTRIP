"""admin routes — /admin (HTML) + /admin/api/* (JSON).

Serves the static console pages (운영 개요 · 수집 이력 · 서비스 헬스 · 게시물 관리) and
the read-only JSON API (A01 §3). Auth is a login page + signed-cookie session:
HTML pages redirect to /admin/login when logged out; /admin/api/* raises 401
(``AdminAuth``). Routes do HTTP I/O only — aggregation lives in ``services``.
"""

from __future__ import annotations

from datetime import date as date_type
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, Form, Query, Request
from fastapi.responses import FileResponse, RedirectResponse, Response

from app.core.db import DbSession
from app.core.ratelimit import rate_limit
from app.core.redis import RedisDep
from app.core.schemas import ok
from app.modules.admin import services
from app.modules.admin.schemas import OverseasVisibilityUpdate
from app.modules.admin.security import SESSION_KEY, AdminAuth, authenticate

_STATIC_DIR = Path(__file__).parent / "static"

router = APIRouter(tags=["ADM · admin console"], include_in_schema=False)

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


def _logged_in(request: Request) -> bool:
    return bool(request.session.get(SESSION_KEY))


@router.get("/login")
async def admin_login_page(request: Request) -> Response:
    """Public login page; redirect to the console if already signed in."""
    if _logged_in(request):
        return RedirectResponse("/admin", status_code=303)
    return _page("login.html")


@router.post(
    "/login",
    dependencies=[Depends(rate_limit(bucket="admin_login", limit=5, window_seconds=60))],
)
async def admin_login_submit(
    request: Request,
    db: DbSession,
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
) -> RedirectResponse:
    """Verify credentials (bcrypt); on success set the session, else bounce back."""
    if not await authenticate(db, username, password):
        return RedirectResponse("/admin/login?error=1", status_code=303)
    request.session[SESSION_KEY] = username
    return RedirectResponse("/admin", status_code=303)


@router.post("/logout")
async def admin_logout(request: Request) -> RedirectResponse:
    """Clear the session and return to the login page."""
    request.session.clear()
    return RedirectResponse("/admin/login", status_code=303)


@router.get("")
@router.get("/")
async def admin_index(request: Request) -> Response:
    """운영 개요 (index.html). Served at both /admin and /admin/."""
    if not _logged_in(request):
        return RedirectResponse("/admin/login", status_code=303)
    return _page("index.html")


@router.get("/history")
async def admin_history(request: Request) -> Response:
    """수집 이력 (history.html)."""
    if not _logged_in(request):
        return RedirectResponse("/admin/login", status_code=303)
    return _page("history.html")


@router.get("/health")
async def admin_health(request: Request) -> Response:
    """서비스 헬스 (health.html)."""
    if not _logged_in(request):
        return RedirectResponse("/admin/login", status_code=303)
    return _page("health.html")


@router.get("/overseas")
async def admin_overseas(request: Request) -> Response:
    """게시물(해외 스팟) 숨김 관리 (overseas.html; A7)."""
    if not _logged_in(request):
        return RedirectResponse("/admin/login", status_code=303)
    return _page("overseas.html")


@router.get("/api/collection")
async def api_collection(_: AdminAuth, db: DbSession) -> dict[str, Any]:
    """CollectionStatus — totalSpots + latest run + next schedule (A01 §2.1)."""
    return ok(await services.get_collection_status(db))


@router.post("/api/collection/trigger")
async def api_collection_trigger(_: AdminAuth, db: DbSession) -> dict[str, Any]:
    """TriggerResult — kick sync-daily (A01 §3 / ADM-009).

    On failure (not configured / GitHub error / already running) the service
    raises AdminTriggerFailed → ADMIN_TRIGGER_FAILED(502) envelope.
    """
    return ok(await services.trigger_collection(db))


@router.get("/api/embedding")
async def api_embedding(_: AdminAuth, db: DbSession, redis: RedisDep) -> dict[str, Any]:
    """EmbeddingStatus — coverage + failure backlog + this-collection progress.

    Embedding is a separate step from collection (CLIP → spot_embeddings), so this
    is its own endpoint rather than folded into /collection.
    """
    return ok(await services.get_embedding_status(db, redis))


@router.post("/api/embedding/trigger")
async def api_embedding_trigger(
    _: AdminAuth,
    redis: RedisDep,
    background_tasks: BackgroundTasks,
    scope: str = Query("failed", pattern="^(failed|missing)$"),
) -> dict[str, Any]:
    """Kick an in-process re-embed job. ``scope=failed`` retries recorded failures;
    ``scope=missing`` processes the (capped) backlog. 502 if already running."""
    return ok(await services.trigger_embedding(redis, background_tasks, scope))


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


@router.get("/api/overseas")
async def api_overseas_list(
    _: AdminAuth,
    db: DbSession,
    q: str | None = Query(None),
    cursor: int | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
) -> dict[str, Any]:
    """OverseasList — id-cursor page, optional name_ko search (A7)."""
    return ok(await services.list_overseas(db, q=q, cursor_id=cursor, limit=limit))


@router.put("/api/overseas/{overseas_id}/visibility")
async def api_overseas_visibility(
    _: AdminAuth, db: DbSession, redis: RedisDep, overseas_id: int, body: OverseasVisibilityUpdate
) -> dict[str, Any]:
    """Toggle overseas_spots.is_hidden; 404 ADMIN_OVERSEAS_NOT_FOUND if absent."""
    return ok(await services.set_overseas_visibility(db, redis, overseas_id, body.isHidden))
