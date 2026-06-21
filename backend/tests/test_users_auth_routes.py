"""Integration tests for the 4 W3 auth/user routes.

Routes under test:
  POST /v1/auth/oauth/kakao
  POST /v1/auth/refresh
  POST /v1/auth/logout
  GET  /v1/users/me

These tests patch ``verify_id_token`` so no real Kakao OIDC network calls occur,
and override the ``get_redis`` FastAPI dependency with ``redis_client_fake``
(in-memory fakeredis) so no real Redis is required.

The ``get_db`` FastAPI dependency is also overridden to use a per-test NullPool
engine wrapped in an outer transaction that is always rolled back at teardown.
Sessions are bound to that connection with ``join_transaction_mode="create_savepoint"``
so service-level ``session.commit()`` calls become savepoints — the outer
rollback undoes everything, preventing row leakage into subsequent tests.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.core.kakao_oidc import KakaoClaims
from app.main import app


@pytest.fixture
def patched_verify():
    """Replace verify_id_token with a fixed KakaoClaims for happy-path tests.

    A unique ``sub`` is generated per test invocation so each test creates a
    distinct user row and tests never collide on the UNIQUE constraint.
    """
    claims = KakaoClaims(
        sub=f"kakao-rt-{uuid.uuid4().hex}",
        email=f"t-{uuid.uuid4().hex[:8]}@e.st",
        nickname="T",
        picture=None,
        nonce=None,
    )
    with patch(
        "app.modules.users.services.verify_id_token",
        AsyncMock(return_value=claims),
    ):
        yield claims


@pytest.fixture(autouse=True)
def override_redis(redis_client_fake):
    """Pipe the FastAPI Redis dependency to the in-memory fakeredis for the test."""
    from app.core.redis import get_redis

    app.dependency_overrides[get_redis] = lambda: redis_client_fake
    yield
    app.dependency_overrides.pop(get_redis, None)


@pytest_asyncio.fixture(autouse=True)
async def override_db():
    """Override get_db with a savepoint-isolated session.

    A single connection per test is wrapped in an outer transaction that is
    always rolled back at teardown.  The inner ``AsyncSession`` uses
    ``join_transaction_mode="create_savepoint"`` so service-level
    ``session.commit()`` demotes to a savepoint flush rather than a real
    COMMIT.  The outer rollback therefore erases every write the test makes,
    preventing row leakage into subsequent tests.
    """
    from app.core.db import get_db

    eng = create_async_engine(str(settings.sqlalchemy_database_url), poolclass=NullPool)
    async with eng.connect() as conn:
        tx = await conn.begin()
        try:

            async def _override():
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
            yield
            app.dependency_overrides.pop(get_db, None)
        finally:
            if tx.is_active:
                await tx.rollback()
    await eng.dispose()


async def test_oauth_kakao_returns_token_pair(client, patched_verify):
    resp = await client.post("/v1/auth/oauth/kakao", json={"idToken": "x"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["accessToken"]
    assert body["data"]["refreshToken"]


async def test_oauth_kakao_bad_token_returns_401(client):
    from app.core.exceptions import OAuthIdTokenInvalid

    with patch(
        "app.modules.users.services.verify_id_token",
        AsyncMock(side_effect=OAuthIdTokenInvalid()),
    ):
        resp = await client.post("/v1/auth/oauth/kakao", json={"idToken": "x"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "OAUTH_ID_TOKEN_INVALID"


async def test_refresh_rotates(client, patched_verify):
    login = (await client.post("/v1/auth/oauth/kakao", json={"idToken": "x"})).json()
    refresh = login["data"]["refreshToken"]
    resp = await client.post("/v1/auth/refresh", json={"refreshToken": refresh})
    assert resp.status_code == 200
    assert resp.json()["data"]["refreshToken"] != refresh


async def test_refresh_malformed_returns_401(client):
    resp = await client.post("/v1/auth/refresh", json={"refreshToken": "not-a-jwt"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "AUTH_TOKEN_INVALID"


async def test_logout_with_valid_refresh_revokes(client, patched_verify):
    login = (await client.post("/v1/auth/oauth/kakao", json={"idToken": "x"})).json()
    refresh = login["data"]["refreshToken"]
    out = await client.post("/v1/auth/logout", json={"refreshToken": refresh})
    assert out.status_code == 200
    # Follow-up refresh on the same token now fails
    after = await client.post("/v1/auth/refresh", json={"refreshToken": refresh})
    assert after.status_code == 401


async def test_logout_with_empty_body_is_idempotent(client):
    resp = await client.post("/v1/auth/logout", json={})
    assert resp.status_code == 200


async def test_logout_with_garbage_token_is_idempotent(client):
    resp = await client.post("/v1/auth/logout", json={"refreshToken": "garbage"})
    assert resp.status_code == 200


async def test_users_me_returns_profile(client, patched_verify):
    login = (await client.post("/v1/auth/oauth/kakao", json={"idToken": "x"})).json()
    access = login["data"]["accessToken"]
    resp = await client.get("/v1/users/me", headers={"Authorization": f"Bearer {access}"})
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "T"


async def test_users_me_without_header_returns_401(client):
    resp = await client.get("/v1/users/me")
    assert resp.status_code == 401
