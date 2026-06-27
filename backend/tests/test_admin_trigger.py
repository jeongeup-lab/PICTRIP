"""ADM-009/010 — collection trigger (POST /admin/api/collection/trigger).

Exercises the trigger endpoint behind the Basic-auth gate (A01 §3): the
``ADMIN_TRIGGER_FAILED(502)`` envelope for the not-configured and concurrency
cases, the happy path (token set, GitHub returns 204), and the structured audit
line (ADM-010).

The actual GitHub ``workflow_dispatch`` HTTP call is mocked at the
``WorkflowDispatchTrigger._dispatch`` boundary so the suite never hits the
network. ``sync_runs`` (pipeline-owned, A05) is created in-transaction with the
measured schema, mirroring ``test_admin_api.py``.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.db import get_db
from app.main import app
from app.modules.admin import triggers

_PASSWORD = "s3cret-admin-pw"
_AUTH = ("admin", _PASSWORD)

# Measured sync_runs schema (A01 §0); same as test_admin_api.py.
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


@pytest.fixture
def admin_password(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setattr(settings, "ADMIN_PASSWORD", _PASSWORD)
    return _PASSWORD


@pytest.fixture
def token_set(monkeypatch: pytest.MonkeyPatch) -> None:
    """Configure the trigger: a non-empty dispatch token = "configured"."""
    monkeypatch.setattr(settings, "GITHUB_DISPATCH_TOKEN", "ghp_test_token")
    monkeypatch.setattr(settings, "GITHUB_REPO", "jeongeup-lab/PICTRIP")
    monkeypatch.setattr(settings, "COLLECTION_WORKFLOW", "pipeline-sync.yml")
    monkeypatch.setattr(settings, "COLLECTION_WORKFLOW_REF", "main")


@pytest.fixture
def token_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "GITHUB_DISPATCH_TOKEN", "")


@pytest.fixture
async def sync_runs_table(db_session: AsyncSession) -> None:
    await db_session.execute(text(_CREATE_SYNC_RUNS))
    await db_session.flush()


async def _insert_run(session: AsyncSession, status: str) -> None:
    await session.execute(
        text(
            "INSERT INTO sync_runs (started_at, finished_at, status, mode) VALUES "
            "(now(), CASE WHEN :st = 'running' THEN NULL ELSE now() END, :st, 'daily')"
        ),
        {"st": status},
    )
    await session.flush()


def _override(db_session: AsyncSession) -> None:
    app.dependency_overrides[get_db] = lambda: db_session


# --- auth gate ----------------------------------------------------------------
@pytest.mark.asyncio
async def test_trigger_requires_auth(client: AsyncClient, admin_password: str) -> None:
    resp = await client.post("/admin/api/collection/trigger")  # no credentials
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "ADMIN_UNAUTHORIZED"


# --- not configured -----------------------------------------------------------
@pytest.mark.asyncio
async def test_trigger_not_configured_502(
    db_session: AsyncSession,
    client: AsyncClient,
    admin_password: str,
    token_unset: None,
    sync_runs_table: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _override(db_session)
    try:
        resp = await client.post("/admin/api/collection/trigger", auth=_AUTH)
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 502
    body = resp.json()
    assert body["error"]["code"] == "ADMIN_TRIGGER_FAILED"
    assert "구성되지 않았습니다" in body["error"]["message"]
    # ADM-010 audit: not-configured path emits a structured line to stdout.
    out = capsys.readouterr().out
    assert "collection.trigger" in out
    assert "result=failed" in out
    assert "reason=not-configured" in out


# --- happy path ---------------------------------------------------------------
@pytest.mark.asyncio
async def test_trigger_happy_path(
    db_session: AsyncSession,
    client: AsyncClient,
    admin_password: str,
    token_set: None,
    sync_runs_table: None,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # GitHub workflow_dispatch returns 204 No Content (no run id) → ref is None.
    dispatched: dict[str, str] = {}

    async def fake_dispatch(self: triggers.WorkflowDispatchTrigger, job: str) -> None:
        dispatched["job"] = job

    monkeypatch.setattr(triggers.WorkflowDispatchTrigger, "_dispatch", fake_dispatch)

    _override(db_session)
    try:
        resp = await client.post("/admin/api/collection/trigger", auth=_AUTH)
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["accepted"] is True
    assert data["job"] == "sync-daily"
    assert data["runId"] is None
    # the adapter was actually invoked with the sync-daily job
    assert dispatched["job"] == "sync-daily"
    # ADM-010 audit: a structured "collection.trigger" line is emitted to stdout
    # (structlog PrintLoggerFactory → stdout, not stdlib logging) with result=accepted.
    out = capsys.readouterr().out
    assert "collection.trigger" in out
    assert "result=accepted" in out


# --- concurrency: already running --------------------------------------------
@pytest.mark.asyncio
async def test_trigger_rejects_when_running(
    db_session: AsyncSession,
    client: AsyncClient,
    admin_password: str,
    token_set: None,
    sync_runs_table: None,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    await _insert_run(db_session, "running")

    called = {"hit": False}

    async def fake_dispatch(self: triggers.WorkflowDispatchTrigger, job: str) -> None:
        called["hit"] = True

    monkeypatch.setattr(triggers.WorkflowDispatchTrigger, "_dispatch", fake_dispatch)

    _override(db_session)
    try:
        resp = await client.post("/admin/api/collection/trigger", auth=_AUTH)
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 502
    body = resp.json()
    assert body["error"]["code"] == "ADMIN_TRIGGER_FAILED"
    assert "진행 중" in body["error"]["message"]
    # GitHub must NOT be called when a run is already in flight.
    assert called["hit"] is False
    # ADM-010 audit: already-running path emits a structured line to stdout.
    out = capsys.readouterr().out
    assert "collection.trigger" in out
    assert "result=failed" in out
    assert "reason=already-running" in out


# --- GitHub returns non-2xx ---------------------------------------------------
@pytest.mark.asyncio
async def test_trigger_github_error_502(
    db_session: AsyncSession,
    client: AsyncClient,
    admin_password: str,
    token_set: None,
    sync_runs_table: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.exceptions import AdminTriggerFailed

    async def fake_dispatch(self: triggers.WorkflowDispatchTrigger, job: str) -> None:
        # Simulate the adapter mapping a non-2xx GitHub response to the domain error.
        raise AdminTriggerFailed("GitHub workflow_dispatch 실패 (HTTP 404).")

    monkeypatch.setattr(triggers.WorkflowDispatchTrigger, "_dispatch", fake_dispatch)

    _override(db_session)
    try:
        resp = await client.post("/admin/api/collection/trigger", auth=_AUTH)
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 502
    assert resp.json()["error"]["code"] == "ADMIN_TRIGGER_FAILED"
