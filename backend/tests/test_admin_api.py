from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.main import app
from app.modules.admin.security import require_admin

_PASSWORD = "admin"
_AUTH = ("admin", _PASSWORD)

_CREATE_SYNC_RUNS = """
CREATE TABLE IF NOT EXISTS sync_runs (
    id            bigserial PRIMARY KEY,
    started_at    timestamptz NOT NULL,
    finished_at   timestamptz,
    status        text NOT NULL,
    mode          text,
    watermark_from timestamptz,
    watermark_to  timestamptz,
    api_calls     integer NOT NULL DEFAULT 0,
    fetched       integer NOT NULL DEFAULT 0,
    inserted      integer NOT NULL DEFAULT 0,
    updated       integer NOT NULL DEFAULT 0,
    soft_deleted  integer NOT NULL DEFAULT 0,
    skipped       integer NOT NULL DEFAULT 0,
    duration_sec  double precision,
    error         text
)
"""


async def _insert_run(
    session: AsyncSession,
    *,
    started_offset_days: int,
    status: str,
    mode: str = "daily",
    api_calls: int = 10,
    inserted: int = 3,
    updated: int = 2,
    soft_deleted: int = 1,
    duration_sec: float | None = 42.5,
    error: str | None = None,
    finished: bool = True,
) -> None:
    await session.execute(
        text(
            "INSERT INTO sync_runs "
            "(started_at, finished_at, status, mode, api_calls, inserted, "
            " updated, soft_deleted, duration_sec, error) VALUES ("
            "  now() - make_interval(days => :off), "
            "  CASE WHEN :fin THEN now() - make_interval(days => :off) + interval '1 minute' "
            "       ELSE NULL END, "
            "  :status, :mode, :api, :ins, :upd, :sd, :dur, :err)"
        ),
        {
            "off": started_offset_days,
            "fin": finished,
            "status": status,
            "mode": mode,
            "api": api_calls,
            "ins": inserted,
            "upd": updated,
            "sd": soft_deleted,
            "dur": duration_sec,
            "err": error,
        },
    )


@pytest.fixture
def admin_password() -> str:
    return _PASSWORD


@pytest.fixture
async def seed(db_session: AsyncSession) -> None:
    await db_session.execute(text(_CREATE_SYNC_RUNS))

    await _insert_run(db_session, started_offset_days=3, status="error")
    await _insert_run(db_session, started_offset_days=1, status="success")
    await _insert_run(
        db_session, started_offset_days=1, status="running", finished=False, duration_sec=None
    )
    await _insert_run(db_session, started_offset_days=0, status="error", api_calls=5, error="boom")
    await _insert_run(
        db_session,
        started_offset_days=0,
        status="success",
        api_calls=11,
        inserted=7,
        updated=4,
        soft_deleted=2,
        duration_sec=63.0,
    )

    for i in range(4):
        await db_session.execute(
            text(
                "INSERT INTO spots (content_id, content_type_id, title, show_flag) "
                "VALUES (:cid, 12, :t, 1)"
            ),
            {"cid": f"sp-{i}", "t": f"spot-{i}"},
        )

    await db_session.execute(
        text(
            "INSERT INTO users (id, created_at, deleted_at) VALUES "
            "(1, now() - interval '2 days', NULL), "
            "(2, now() - interval '1 day',  NULL), "
            "(3, now() - interval '40 days', NULL), "
            "(4, now() - interval '40 days', now() - interval '5 days')"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO user_auth_providers (user_id, provider, provider_user_id) VALUES "
            "(1, 'kakao', 'k1'), (2, 'kakao', 'k2'), (3, 'google', 'g1')"
        )
    )
    await db_session.flush()


def _override(db_session: AsyncSession) -> None:
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[require_admin] = lambda: "admin"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        "/admin/api/collection",
        "/admin/api/history",
        "/admin/api/history/2026-06-25",
        "/admin/api/health",
    ],
)
async def test_api_requires_auth(client: AsyncClient, admin_password: str, path: str) -> None:
    resp = await client.get(path)
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "ADMIN_UNAUTHORIZED"


@pytest.mark.asyncio
async def test_collection_status(
    db_session: AsyncSession, client: AsyncClient, admin_password: str, seed: None
) -> None:
    _override(db_session)
    try:
        resp = await client.get("/admin/api/collection", auth=_AUTH)
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["totalSpots"] == 4
    assert data["source"]["name"] == "국문 관광정보 서비스"
    assert data["source"]["endpoint"] == "areaBasedSyncList2"
    assert data["nextScheduledAt"] is None

    last = data["source"]["lastRun"]
    assert last["status"] == "success"
    assert last["apiCalls"] == 11
    assert last["inserted"] == 7
    assert last["updated"] == 4
    assert last["softDeleted"] == 2
    assert last["durationSec"] == 63.0
    assert last["finishedAt"] is not None
    assert last["ranAt"] is not None
    assert set(last.keys()) == {
        "status",
        "finishedAt",
        "ranAt",
        "apiCalls",
        "inserted",
        "updated",
        "softDeleted",
        "durationSec",
    }


@pytest.mark.asyncio
async def test_history_grouping_7d(
    db_session: AsyncSession, client: AsyncClient, admin_password: str, seed: None
) -> None:
    _override(db_session)
    try:
        resp = await client.get("/admin/api/history?days=7", auth=_AUTH)
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    days = resp.json()["data"]["days"]
    assert len(days) == 3
    by_runs = {d["date"]: d for d in days}
    assert days[0]["date"] >= days[1]["date"] >= days[2]["date"]
    today = days[0]
    assert today["success"] == 1
    assert today["error"] == 1
    assert today["running"] == 0
    assert today["runs"] == 2
    running_day = next(d for d in days if d["running"] == 1)
    assert running_day["success"] == 1
    assert running_day["runs"] == 2
    assert set(by_runs[today["date"]].keys()) == {
        "date",
        "success",
        "error",
        "running",
        "runs",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("days", [0, 200])
async def test_history_days_out_of_bounds_422(
    db_session: AsyncSession, client: AsyncClient, admin_password: str, days: int
) -> None:
    _override(db_session)
    try:
        resp = await client.get(f"/admin/api/history?days={days}", auth=_AUTH)
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_FAILED"


@pytest.mark.asyncio
async def test_history_window_2d_excludes_old(
    db_session: AsyncSession, client: AsyncClient, admin_password: str, seed: None
) -> None:
    _override(db_session)
    try:
        resp = await client.get("/admin/api/history?days=2", auth=_AUTH)
    finally:
        app.dependency_overrides.clear()

    days = resp.json()["data"]["days"]
    assert len(days) == 2


@pytest.mark.asyncio
async def test_history_detail_today(
    db_session: AsyncSession, client: AsyncClient, admin_password: str, seed: None
) -> None:
    today = (await db_session.execute(text("SELECT CURRENT_DATE"))).scalar_one()
    _override(db_session)
    try:
        resp = await client.get(f"/admin/api/history/{today.isoformat()}", auth=_AUTH)
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["date"] == today.isoformat()
    assert len(data["runs"]) == 2
    statuses = {r["status"] for r in data["runs"]}
    assert statuses == {"success", "error"}
    run = data["runs"][0]
    assert set(run.keys()) == {
        "id",
        "status",
        "mode",
        "startedAt",
        "finishedAt",
        "apiCalls",
        "inserted",
        "updated",
        "softDeleted",
        "durationSec",
        "error",
    }


@pytest.mark.asyncio
async def test_history_detail_unknown_date_404(
    db_session: AsyncSession, client: AsyncClient, admin_password: str, seed: None
) -> None:
    _override(db_session)
    try:
        resp = await client.get("/admin/api/history/1999-01-01", auth=_AUTH)
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "ADMIN_HISTORY_NOT_FOUND"


@pytest.mark.asyncio
async def test_health(
    db_session: AsyncSession, client: AsyncClient, admin_password: str, seed: None
) -> None:
    _override(db_session)
    try:
        resp = await client.get("/admin/api/health", auth=_AUTH)
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()["data"]

    assert data["db"]["ok"] is True
    assert data["db"]["spots"] == 4
    assert isinstance(data["db"]["poolSize"], int)
    assert isinstance(data["db"]["poolInUse"], int)

    assert data["api"]["version"]
    assert isinstance(data["api"]["uptimeSec"], int)
    assert data["api"]["p95Ms"] is None

    assert data["tunnel"] == {"ok": None, "detail": None}

    users = data["users"]
    assert users["total"] == 4
    assert users["active"] == 3
    assert users["new7d"] == 2
    assert users["deleted30d"] == 1
    assert users["kakao"] == 2
