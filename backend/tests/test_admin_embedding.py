"""ADM embedding status + re-embed trigger (collection/embedding are separate).

GET /admin/api/embedding surfaces coverage, the failure backlog, and the
"this collection" progress (spots synced since the latest sync run). POST
/admin/api/embedding/trigger kicks an in-process job guarded by a Redis lock.

``sync_runs`` (pipeline-owned, A05) is created in-transaction with the measured
schema, mirroring test_admin_api.py. The embed job itself is monkeypatched in the
trigger tests so no CLIP/model/network is touched.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.redis import get_redis
from app.main import app
from app.modules.admin import services
from app.modules.admin.security import require_admin

_AUTH = ("admin", "admin")

_CREATE_SYNC_RUNS = """
CREATE TABLE IF NOT EXISTS sync_runs (
    id            bigserial PRIMARY KEY,
    started_at    timestamptz NOT NULL,
    finished_at   timestamptz,
    status        text NOT NULL,
    mode          text,
    api_calls     integer NOT NULL DEFAULT 0,
    inserted      integer NOT NULL DEFAULT 0,
    updated       integer NOT NULL DEFAULT 0,
    soft_deleted  integer NOT NULL DEFAULT 0,
    duration_sec  double precision,
    error         text
)
"""

_VEC = "[" + ",".join(["0.0"] * 512) + "]"


@pytest.fixture
def admin_password() -> str:
    return "admin"


async def _seed_spot(
    session: AsyncSession, cid: str, url: str | None, *, days_ago: int = 5
) -> None:
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, first_image_url, "
            "show_flag, synced_at) VALUES "
            "(:c, 12, :t, :u, 1, now() - make_interval(days => :d))"
        ),
        {"c": cid, "t": cid, "u": url, "d": days_ago},
    )


@pytest.fixture
async def seed(db_session: AsyncSession) -> None:
    await db_session.execute(text(_CREATE_SYNC_RUNS))
    await db_session.execute(
        text(
            "INSERT INTO sync_runs (started_at, finished_at, status, mode) VALUES "
            "(now() - interval '1 day', now() - interval '1 day', 'success', 'daily')"
        )
    )

    await _seed_spot(db_session, "emb-old", "https://img/1.jpg", days_ago=10)
    await _seed_spot(db_session, "emb-new", "https://img/2.jpg", days_ago=0)
    await _seed_spot(db_session, "fail-1", "https://img/3.jpg", days_ago=0)
    await _seed_spot(db_session, "pend-1", "https://img/4.jpg", days_ago=0)
    await _seed_spot(db_session, "noimg", None, days_ago=0)

    for cid, image_url in (
        ("emb-old", "https://img/1.jpg"),
        ("emb-new", "https://img/2.jpg"),
    ):
        await db_session.execute(
            text(
                "INSERT INTO spot_embeddings (content_id, embedding, image_url) VALUES (:c, :v, :u)"
            ),
            {"c": cid, "v": _VEC, "u": image_url},
        )
    await db_session.execute(
        text(
            "INSERT INTO spot_embeddings (content_id, embedding, image_url) "
            "VALUES ('pend-1', :v, 'https://img/stale.jpg')"
        ),
        {"v": _VEC},
    )
    await db_session.execute(
        text(
            "INSERT INTO embedding_failures (content_id, reason, attempts) "
            "VALUES ('fail-1', 'download_failed', 3)"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO embedding_failures (content_id, reason, attempts) "
            "VALUES ('noimg', 'clip_error', 2)"
        )
    )
    await db_session.flush()


def _override(db_session: AsyncSession, redis) -> None:
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[require_admin] = lambda: "admin"
    app.dependency_overrides[get_redis] = lambda: redis


@pytest.mark.asyncio
async def test_embedding_requires_auth(client: AsyncClient, admin_password: str) -> None:
    resp = await client.get("/admin/api/embedding")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "ADMIN_UNAUTHORIZED"


@pytest.mark.asyncio
async def test_embedding_status(
    db_session: AsyncSession,
    client: AsyncClient,
    admin_password: str,
    seed: None,
    redis_client_fake,
) -> None:
    _override(db_session, redis_client_fake)
    try:
        resp = await client.get("/admin/api/embedding", auth=_AUTH)
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["totalSpots"] == 5
    assert data["withImage"] == 4
    assert data["embedded"] == 2
    assert data["missing"] == 2
    assert data["failed"] == 1
    assert data["pending"] == 1
    assert data["failuresByReason"] == {"download_failed": 1}
    assert data["running"] is False
    assert data["lastComputedAt"] is not None

    rec = data["recent"]
    assert rec["since"] is not None
    assert rec["target"] == 3
    assert rec["embedded"] == 1
    assert rec["outstanding"] == 2

    assert set(data.keys()) == {
        "totalSpots",
        "withImage",
        "embedded",
        "missing",
        "failed",
        "pending",
        "failuresByReason",
        "recent",
        "lastComputedAt",
        "running",
    }


@pytest.mark.asyncio
async def test_embedding_status_running_reflects_lock(
    db_session: AsyncSession,
    client: AsyncClient,
    admin_password: str,
    seed: None,
    redis_client_fake,
) -> None:
    await redis_client_fake.set("admin:embed:running", "admin")
    _override(db_session, redis_client_fake)
    try:
        resp = await client.get("/admin/api/embedding", auth=_AUTH)
    finally:
        app.dependency_overrides.clear()
    assert resp.json()["data"]["running"] is True


@pytest.mark.asyncio
async def test_trigger_happy_path_schedules_job(
    db_session: AsyncSession,
    client: AsyncClient,
    admin_password: str,
    redis_client_fake,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls: dict[str, object] = {}

    async def fake_job(**kwargs: object) -> object:
        assert await redis_client_fake.get("matching:revision") == "1"
        calls.update(kwargs)
        await redis_client_fake.set("match:1:during", "cached")
        return None

    monkeypatch.setattr(services.image_services, "run_embedding_job", fake_job)
    await redis_client_fake.set("match:0:before", "cached")

    _override(db_session, redis_client_fake)
    try:
        resp = await client.post("/admin/api/embedding/trigger?scope=failed", auth=_AUTH)
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data == {"job": "embed-failed", "scope": "failed", "accepted": True}
    assert calls.get("only_failed") is True
    assert await redis_client_fake.get("matching:revision") == "2"
    assert await redis_client_fake.get("match:1:during") == "cached"
    assert await redis_client_fake.exists("admin:embed:running") == 0
    out = capsys.readouterr().out
    assert "embedding.trigger" in out
    assert "result=accepted" in out


@pytest.mark.asyncio
async def test_embed_job_runs_when_match_cache_revision_bump_fails(
    redis_client_fake, monkeypatch: pytest.MonkeyPatch
) -> None:
    ran = False

    async def broken_incr(*args: object, **kwargs: object) -> int:
        raise ConnectionError("redis unavailable")

    async def fake_job(**kwargs: object) -> None:
        nonlocal ran
        ran = True

    monkeypatch.setattr(redis_client_fake, "incr", broken_incr)
    monkeypatch.setattr(services.image_services, "run_embedding_job", fake_job)
    lock = await services.image_services.acquire_embedding_job_lock(redis_client_fake)
    assert lock is not None

    await services._run_embed_job(redis_client_fake, only_failed=False, limit=10, lock=lock)

    assert ran is True
    assert await redis_client_fake.exists("admin:embed:running") == 0


@pytest.mark.asyncio
async def test_trigger_rejects_when_locked(
    db_session: AsyncSession,
    client: AsyncClient,
    admin_password: str,
    redis_client_fake,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await redis_client_fake.set("admin:embed:running", "admin")
    ran = {"hit": False}

    async def fake_job(**kwargs: object) -> object:
        ran["hit"] = True
        return None

    monkeypatch.setattr(services.image_services, "run_embedding_job", fake_job)

    _override(db_session, redis_client_fake)
    try:
        resp = await client.post("/admin/api/embedding/trigger?scope=missing", auth=_AUTH)
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 502
    assert resp.json()["error"]["code"] == "ADMIN_TRIGGER_FAILED"
    assert "진행 중" in resp.json()["error"]["message"]
    assert ran["hit"] is False


@pytest.mark.asyncio
async def test_trigger_invalid_scope_422(
    db_session: AsyncSession, client: AsyncClient, admin_password: str, redis_client_fake
) -> None:
    _override(db_session, redis_client_fake)
    try:
        resp = await client.post("/admin/api/embedding/trigger?scope=bogus", auth=_AUTH)
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 422
