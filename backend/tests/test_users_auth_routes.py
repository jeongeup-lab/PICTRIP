"""Integration tests for the auth/user routes (oauth/refresh/logout, GET /users/me)."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.core.oidc import OidcClaims
from app.main import app


@pytest.fixture
def patched_verify():
    # Unique sub per invocation so tests never collide on the provider UNIQUE constraint.
    claims = OidcClaims(
        sub=f"kakao-rt-{uuid.uuid4().hex}",
        email=f"t-{uuid.uuid4().hex[:8]}@e.st",
        name="T",
        picture=None,
    )
    with patch(
        "app.modules.users.services.verify_oauth_id_token",
        AsyncMock(return_value=claims),
    ):
        yield claims


@pytest.fixture(autouse=True)
def override_redis(redis_client_fake):
    from app.core.redis import get_redis

    app.dependency_overrides[get_redis] = lambda: redis_client_fake
    yield
    app.dependency_overrides.pop(get_redis, None)


@pytest_asyncio.fixture(autouse=True)
async def override_db():
    # Savepoint-isolated session: service commits demote to savepoints, the outer rollback erases all writes.
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
        "app.modules.users.services.verify_oauth_id_token",
        AsyncMock(side_effect=OAuthIdTokenInvalid()),
    ):
        resp = await client.post("/v1/auth/oauth/kakao", json={"idToken": "x"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "OAUTH_ID_TOKEN_INVALID"


async def test_refresh_returns_valid_pair_without_rotation(client, patched_verify):
    login = (await client.post("/v1/auth/oauth/kakao", json={"idToken": "x"})).json()
    refresh = login["data"]["refreshToken"]
    resp = await client.post("/v1/auth/refresh", json={"refreshToken": refresh})
    assert resp.status_code == 200
    assert resp.json()["data"]["refreshToken"]
    # Denylist model: refresh does NOT rotate, so the original token still works.
    again = await client.post("/v1/auth/refresh", json={"refreshToken": refresh})
    assert again.status_code == 200


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
    body = resp.json()["data"]
    assert body["displayName"] == "T"
    assert "avatarUrl" in body
    assert "name" not in body and "profileImageUrl" not in body


async def test_users_me_without_header_returns_401(client):
    resp = await client.get("/v1/users/me")
    assert resp.status_code == 401
