"""Integration tests for DELETE /v1/users/me (account deletion).

App Store/Play review 5.1.1(v) requires real in-app deletion: soft-delete but scrub
PII and unlink auth providers so the account is genuinely gone.
"""

from __future__ import annotations

import uuid
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


@pytest.fixture(autouse=True)
def override_redis(redis_client_fake):
    from app.core.redis import get_redis

    app.dependency_overrides[get_redis] = lambda: redis_client_fake
    yield
    app.dependency_overrides.pop(get_redis, None)


@pytest_asyncio.fixture(autouse=True)
async def override_db_and_seed() -> AsyncIterator[AsyncSession]:
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


async def _seed_user_with_provider(session: AsyncSession) -> int:
    email = f"del-{uuid.uuid4().hex[:10]}@e.st"
    row = (
        await session.execute(
            text("INSERT INTO users (email, name) VALUES (:e, '탈퇴유저') RETURNING id"),
            {"e": email},
        )
    ).first()
    assert row is not None
    uid = int(row.id)
    await session.execute(
        text(
            "INSERT INTO user_auth_providers (user_id, provider, provider_user_id) "
            "VALUES (:u, 'kakao', :pid)"
        ),
        {"u": uid, "pid": f"kakao-{uuid.uuid4().hex}"},
    )
    await session.commit()
    return uid


def _auth(user_id: int) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id=user_id)}"}


@pytest.mark.asyncio
async def test_delete_anonymizes_unlinks_and_blocks_profile(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    uid = await _seed_user_with_provider(override_db_and_seed)

    resp = await client.delete("/v1/users/me", headers=_auth(uid))
    assert resp.status_code == 204
    assert resp.content == b""

    row = (
        await override_db_and_seed.execute(
            text("SELECT email, name, deleted_at FROM users WHERE id = :u"), {"u": uid}
        )
    ).first()
    assert row is not None
    assert row.deleted_at is not None  # soft-deleted
    assert row.email is None and row.name is None  # PII scrubbed

    providers = (
        await override_db_and_seed.execute(
            text("SELECT count(*) AS n FROM user_auth_providers WHERE user_id = :u"), {"u": uid}
        )
    ).scalar_one()
    assert providers == 0  # OAuth unlinked

    # The token still decodes, but the user is now deleted → profile is blocked.
    me = await client.get("/v1/users/me", headers=_auth(uid))
    assert me.status_code == 401
    assert me.json()["error"]["code"] == "AUTH_TOKEN_INVALID"


@pytest.mark.asyncio
async def test_delete_clears_password_and_blocks_email_login(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    email = f"pw-{uuid.uuid4().hex[:10]}@e.st"
    password = "correct-horse-battery"  # test fixture, not a real secret

    signup = await client.post(
        "/v1/auth/email/signup",
        json={"email": email, "password": password, "name": "비번유저"},
    )
    assert signup.status_code == 201
    uid = signup.json()["data"]["user"]["id"]

    # Sanity: the credential exists and login works before deletion.
    pre = await client.post("/v1/auth/email/login", json={"email": email, "password": password})
    assert pre.status_code == 200

    resp = await client.delete("/v1/users/me", headers=_auth(uid))
    assert resp.status_code == 204

    row = (
        await override_db_and_seed.execute(
            text("SELECT password_hash, deleted_at FROM users WHERE id = :u"), {"u": uid}
        )
    ).first()
    assert row is not None
    assert row.deleted_at is not None  # soft-deleted
    assert row.password_hash is None  # credential cleared

    # The email login can no longer authenticate this account.
    post = await client.post("/v1/auth/email/login", json={"email": email, "password": password})
    assert post.status_code == 401
    assert post.json()["error"]["code"] == "AUTH_INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_delete_is_idempotent(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    uid = await _seed_user_with_provider(override_db_and_seed)

    first = await client.delete("/v1/users/me", headers=_auth(uid))
    assert first.status_code == 204

    # A second call with the same (still-valid-signature) token is a no-op 204.
    second = await client.delete("/v1/users/me", headers=_auth(uid))
    assert second.status_code == 204


@pytest.mark.asyncio
async def test_delete_without_auth_returns_401(client: AsyncClient) -> None:
    resp = await client.delete("/v1/users/me")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "AUTH_TOKEN_INVALID"
