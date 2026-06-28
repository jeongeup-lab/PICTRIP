"""ADM Phase 1 — read-only JSON API (A01 §3).

Exercises the four endpoints (collection · history · history/{date} · health)
behind the Basic-auth gate, asserting the exact §3 camelCase payload shapes and
the date-grouping / 404 / aggregate semantics.

``sync_runs`` is owned by pipeline/ and is NOT a backend model or Alembic table
(monorepo invariant), so the test DB has no such table. We create it inside the
rolled-back test transaction with the measured schema (A01 §0): timestamptz for
the time columns, int counters, ``double precision`` duration_sec, ``text`` error.
Everything is seeded via raw ``text()`` and discarded on rollback.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.main import app
from app.modules.admin.security import require_admin

# DB-backed admin auth: migration 0016 seeds admin/admin into the test DB
# (alembic upgrade head runs before pytest in CI), so requests authenticate with
# this fixed credential — no settings monkeypatch.
_PASSWORD = "admin"
_AUTH = ("admin", _PASSWORD)

# Measured sync_runs schema (A01 §0). Created per-test so the suite is self-
# contained on a DB that pipeline/ has never touched.
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
    """Insert one run started ``started_offset_days`` ago (relative to now())."""
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
    """The DB-seeded default admin credential (migration 0016)."""
    return _PASSWORD


@pytest.fixture
async def seed(db_session: AsyncSession) -> None:
    # sync_runs (foreign/pipeline-owned) created in-transaction.
    await db_session.execute(text(_CREATE_SYNC_RUNS))

    # Insert oldest → newest so the serial id ascends with recency (as the daily
    # pipeline does). The last-inserted row (today's success) is therefore the
    # highest id, which is exactly what /collection's "ORDER BY id DESC" lastRun
    # must surface (A01 §2.1).
    #
    # 3 days ago: one error (inside a 7d window, outside a 2d window).
    await _insert_run(db_session, started_offset_days=3, status="error")
    # Yesterday: success + running (unfinished).
    await _insert_run(db_session, started_offset_days=1, status="success")
    await _insert_run(
        db_session, started_offset_days=1, status="running", finished=False, duration_sec=None
    )
    # Today: error then the latest success run (highest id → drives lastRun).
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

    # spots — totalSpots / health.db.spots = 4.
    for i in range(4):
        await db_session.execute(
            text(
                "INSERT INTO spots (content_id, content_type_id, title, show_flag) "
                "VALUES (:cid, 12, :t, 1)"
            ),
            {"cid": f"sp-{i}", "t": f"spot-{i}"},
        )

    # users — total=4, active(deleted_at IS NULL)=3, new7d=2 (created recently),
    # deleted30d=1, kakao=2.
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


# --- auth gate ----------------------------------------------------------------
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
    resp = await client.get(path)  # no credentials
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "ADMIN_UNAUTHORIZED"


# --- /admin/api/collection ----------------------------------------------------
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
    # Highest-id row = today's success run with the bumped counters.
    assert last["status"] == "success"
    assert last["apiCalls"] == 11
    assert last["inserted"] == 7
    assert last["updated"] == 4
    assert last["softDeleted"] == 2
    assert last["durationSec"] == 63.0
    assert last["finishedAt"] is not None
    assert last["ranAt"] is not None  # = finishedAt here
    # camelCase contract — no snake_case leaks.
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


# --- /admin/api/history -------------------------------------------------------
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
    # 3 distinct days seeded within 7d (today, -1, -3).
    assert len(days) == 3
    by_runs = {d["date"]: d for d in days}
    # most-recent-first ordering
    assert days[0]["date"] >= days[1]["date"] >= days[2]["date"]
    # today: 1 success + 1 error
    today = days[0]
    assert today["success"] == 1
    assert today["error"] == 1
    assert today["running"] == 0
    assert today["runs"] == 2
    # the -1 day has a running run
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
    """days is bounded to [1, 90]; out-of-range → 422 (after the DB-backed auth gate).

    get_db is overridden so the auth lookup uses the per-test session, not the
    module engine (which would leak a connection across the function-scoped loop).
    """
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
    # days=2 → today + yesterday only; the -3d error row is excluded.
    assert len(days) == 2


# --- /admin/api/history/{date} ------------------------------------------------
@pytest.mark.asyncio
async def test_history_detail_today(
    db_session: AsyncSession, client: AsyncClient, admin_password: str, seed: None
) -> None:
    # resolve "today" via the DB to avoid TZ skew between Python and Postgres.
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


# --- /admin/api/health --------------------------------------------------------
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

    assert data["api"]["version"]  # present, non-empty
    assert isinstance(data["api"]["uptimeSec"], int)
    assert data["api"]["p95Ms"] is None

    assert data["tunnel"] == {"ok": None, "detail": None}

    users = data["users"]
    assert users["total"] == 4
    assert users["active"] == 3
    assert users["new7d"] == 2
    assert users["deleted30d"] == 1
    assert users["kakao"] == 2
