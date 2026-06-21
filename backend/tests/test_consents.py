"""Integration tests for the consent route.

Route under test:
  PUT /v1/users/me/consents  — upsert the user's consent row (PK user_id)

The endpoint is protected: auth is exercised end-to-end by seeding a real user
row and minting a real access token via ``create_access_token``. The pattern
mirrors tests/test_users_saved_spots_routes.py — a per-test override binds both
the FastAPI ``get_db`` dependency and the seed session to a single connection
wrapped in an outer transaction that is rolled back on teardown.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.core.auth import create_access_token


@pytest_asyncio.fixture(autouse=True)
async def override_db_and_seed() -> AsyncIterator[AsyncSession]:
    from app.core.db import get_db
    from app.main import app

    eng = create_async_engine(settings.sqlalchemy_database_url, poolclass=NullPool)
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


async def _seed_user(session: AsyncSession) -> int:
    email = f"consent-{uuid.uuid4().hex[:10]}@e.st"
    row = (
        await session.execute(
            text("INSERT INTO users (email, name) VALUES (:e, 'Consenter') RETURNING id"),
            {"e": email},
        )
    ).first()
    assert row is not None
    await session.commit()
    return int(row.id)


def _auth(user_id: int) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id=user_id)}"}


async def test_put_consents_creates_and_echoes(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    uid = await _seed_user(override_db_and_seed)

    resp = await client.put(
        "/v1/users/me/consents",
        headers=_auth(uid),
        json={"locationConsent": True, "termsVersion": "v1.0"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["error"] is None
    data = body["data"]
    assert data["locationConsent"] is True
    assert data["photoConsent"] is False  # default
    assert data["termsVersion"] == "v1.0"
    assert data["consentedAt"] is not None


async def test_put_consents_with_photo_consent(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    uid = await _seed_user(override_db_and_seed)

    resp = await client.put(
        "/v1/users/me/consents",
        headers=_auth(uid),
        json={"locationConsent": True, "photoConsent": True, "termsVersion": "v2.0"},
    )

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["locationConsent"] is True
    assert data["photoConsent"] is True
    assert data["termsVersion"] == "v2.0"


async def test_put_consents_is_idempotent_upsert(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    uid = await _seed_user(override_db_and_seed)

    first = await client.put(
        "/v1/users/me/consents",
        headers=_auth(uid),
        json={"locationConsent": True, "photoConsent": True, "termsVersion": "v1.0"},
    )
    assert first.status_code == 200

    # A second PUT updates the SAME row in place (PK = user_id).
    second = await client.put(
        "/v1/users/me/consents",
        headers=_auth(uid),
        json={"locationConsent": False, "photoConsent": False, "termsVersion": "v3.0"},
    )
    assert second.status_code == 200
    data = second.json()["data"]
    assert data["locationConsent"] is False
    assert data["photoConsent"] is False
    assert data["termsVersion"] == "v3.0"

    # Exactly one row persists for this user.
    count = (
        await override_db_and_seed.execute(
            text("SELECT count(*) AS n FROM user_consents WHERE user_id = :u"), {"u": uid}
        )
    ).scalar_one()
    assert count == 1


async def test_put_consents_without_auth_returns_401(client: AsyncClient) -> None:
    resp = await client.put(
        "/v1/users/me/consents",
        json={"locationConsent": True, "termsVersion": "v1.0"},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "AUTH_TOKEN_INVALID"
