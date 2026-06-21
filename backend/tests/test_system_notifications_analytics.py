"""Integration tests for SYS notification-preference + analytics endpoints.

Covers API spec §12 SYS surface added by ADR-0013:
    GET  /v1/me/notifications      → prefs (creating a default consent row if none)
    PUT  /v1/me/notifications      → update + persist the master toggle
    POST /v1/analytics/events      → record a client analytics event

Run against pictrip_test (PROMPT §3). The override_db fixture wraps every test in
an outer transaction that is always rolled back, so inserted rows never leak.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.core.auth import create_access_token
from app.main import app


@pytest_asyncio.fixture(autouse=True)
async def override_db() -> AsyncIterator[AsyncSession]:
    from app.core.db import get_db

    eng = create_async_engine(str(settings.sqlalchemy_database_url), poolclass=NullPool)
    async with eng.connect() as conn:
        tx = await conn.begin()
        try:
            seed = AsyncSession(
                bind=conn,
                expire_on_commit=False,
                join_transaction_mode="create_savepoint",
            )

            async def _override() -> AsyncIterator[AsyncSession]:
                session = AsyncSession(
                    bind=conn,
                    expire_on_commit=False,
                    join_transaction_mode="create_savepoint",
                )
                try:
                    yield session
                finally:
                    await session.close()

            app.dependency_overrides[get_db] = _override
            try:
                yield seed
            finally:
                await seed.close()
                app.dependency_overrides.pop(get_db, None)
        finally:
            if tx.is_active:
                await tx.rollback()
    await eng.dispose()


async def _make_user(session: AsyncSession) -> int:
    row = await session.execute(
        text("INSERT INTO users (email, name) VALUES (:e, :n) RETURNING id"),
        {"e": None, "n": "sys-test-user"},
    )
    user_id = int(row.scalar_one())
    await session.commit()
    return user_id


def _auth(user_id: int) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id=user_id)}"}


# --------------------------------------------------------------------------- #
# GET /me/notifications                                                        #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_get_notifications_creates_defaults_when_none(
    client: AsyncClient, override_db: AsyncSession
) -> None:
    user_id = await _make_user(override_db)

    resp = await client.get("/v1/me/notifications", headers=_auth(user_id))

    assert resp.status_code == 200
    body = resp.json()
    assert body["error"] is None
    data = body["data"]
    # server_default for notification_consent is false → default-created prefs are off.
    assert data["enabled"] is False
    assert isinstance(data["categories"], list)
    assert "course_rec" in data["categories"]

    # A default consent row was actually persisted.
    persisted = await override_db.scalar(
        text("SELECT notification_consent FROM user_consents WHERE user_id = :u"),
        {"u": user_id},
    )
    assert persisted is False


@pytest.mark.asyncio
async def test_get_notifications_requires_auth(client: AsyncClient) -> None:
    resp = await client.get("/v1/me/notifications")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "AUTH_TOKEN_INVALID"


# --------------------------------------------------------------------------- #
# PUT /me/notifications                                                        #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_put_notifications_updates_and_persists(
    client: AsyncClient, override_db: AsyncSession
) -> None:
    user_id = await _make_user(override_db)

    resp = await client.put("/v1/me/notifications", json={"enabled": True}, headers=_auth(user_id))
    assert resp.status_code == 200
    assert resp.json()["data"]["enabled"] is True

    persisted = await override_db.scalar(
        text("SELECT notification_consent FROM user_consents WHERE user_id = :u"),
        {"u": user_id},
    )
    assert persisted is True

    # Toggling back off persists too.
    resp2 = await client.put(
        "/v1/me/notifications", json={"enabled": False}, headers=_auth(user_id)
    )
    assert resp2.status_code == 200
    assert resp2.json()["data"]["enabled"] is False


@pytest.mark.asyncio
async def test_put_notifications_requires_auth(client: AsyncClient) -> None:
    resp = await client.put("/v1/me/notifications", json={"enabled": True})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_put_notifications_validation_error(
    client: AsyncClient, override_db: AsyncSession
) -> None:
    user_id = await _make_user(override_db)
    resp = await client.put(
        "/v1/me/notifications", json={"enabled": "not-a-bool"}, headers=_auth(user_id)
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_FAILED"


# --------------------------------------------------------------------------- #
# POST /analytics/events                                                       #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_post_analytics_event_records_row(
    client: AsyncClient, override_db: AsyncSession
) -> None:
    user_id = await _make_user(override_db)

    resp = await client.post(
        "/v1/analytics/events",
        json={"eventName": "photo_search_started", "properties": {"source": "home"}},
        headers=_auth(user_id),
    )
    assert resp.status_code == 202
    assert resp.json()["data"]["recorded"] is True

    count = await override_db.scalar(
        text("SELECT count(*) FROM analytics_events WHERE user_id = :u AND event_name = :e"),
        {"u": user_id, "e": "photo_search_started"},
    )
    assert count == 1


@pytest.mark.asyncio
async def test_post_analytics_event_allows_null_properties(
    client: AsyncClient, override_db: AsyncSession
) -> None:
    user_id = await _make_user(override_db)
    resp = await client.post(
        "/v1/analytics/events",
        json={"eventName": "app_opened"},
        headers=_auth(user_id),
    )
    assert resp.status_code == 202


@pytest.mark.asyncio
async def test_post_analytics_event_requires_auth(client: AsyncClient) -> None:
    resp = await client.post("/v1/analytics/events", json={"eventName": "app_opened"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_post_analytics_event_validation_error(
    client: AsyncClient, override_db: AsyncSession
) -> None:
    user_id = await _make_user(override_db)
    # eventName exceeds the 64-char column / schema limit.
    resp = await client.post(
        "/v1/analytics/events",
        json={"eventName": "x" * 65},
        headers=_auth(user_id),
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_FAILED"
