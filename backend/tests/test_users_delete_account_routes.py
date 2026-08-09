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
from app.main import app
from app.security.jwt import create_access_token, create_refresh_token


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
    assert row.deleted_at is not None
    assert row.email is None and row.name is None

    providers = (
        await override_db_and_seed.execute(
            text("SELECT count(*) AS n FROM user_auth_providers WHERE user_id = :u"), {"u": uid}
        )
    ).scalar_one()
    assert providers == 0

    me = await client.get("/v1/users/me", headers=_auth(uid))
    assert me.status_code == 401
    assert me.json()["error"]["code"] == "AUTH_TOKEN_INVALID"


@pytest.mark.asyncio
async def test_delete_clears_a_legacy_email_password(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    email = f"pw-{uuid.uuid4().hex[:10]}@e.st"
    row = (
        await override_db_and_seed.execute(
            text(
                "INSERT INTO users (email, name, password_hash) "
                "VALUES (:e, '비번유저', 'legacy-hash') RETURNING id"
            ),
            {"e": email},
        )
    ).first()
    assert row is not None
    uid = int(row.id)
    await override_db_and_seed.commit()

    resp = await client.delete("/v1/users/me", headers=_auth(uid))
    assert resp.status_code == 204

    after = (
        await override_db_and_seed.execute(
            text("SELECT password_hash, deleted_at FROM users WHERE id = :u"), {"u": uid}
        )
    ).first()
    assert after is not None
    assert after.deleted_at is not None
    assert after.password_hash is None


@pytest.mark.asyncio
async def test_delete_is_idempotent(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    uid = await _seed_user_with_provider(override_db_and_seed)

    first = await client.delete("/v1/users/me", headers=_auth(uid))
    assert first.status_code == 204

    second = await client.delete("/v1/users/me", headers=_auth(uid))
    assert second.status_code == 204


@pytest.mark.asyncio
async def test_delete_destroys_saved_spots(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    uid = await _seed_user_with_provider(override_db_and_seed)
    content_id = f"del-{uuid.uuid4().hex[:8]}"
    await override_db_and_seed.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, show_flag) "
            "VALUES (:c, 12, '탈퇴검증', 1) ON CONFLICT (content_id) DO NOTHING"
        ),
        {"c": content_id},
    )
    await override_db_and_seed.execute(
        text("INSERT INTO user_saved_spots (user_id, content_id) VALUES (:u, :c)"),
        {"u": uid, "c": content_id},
    )
    await override_db_and_seed.commit()

    resp = await client.delete("/v1/users/me", headers=_auth(uid))
    assert resp.status_code == 204

    left = await override_db_and_seed.scalar(
        text("SELECT count(*) FROM user_saved_spots WHERE user_id = :u"), {"u": uid}
    )
    assert left == 0


@pytest.mark.asyncio
async def test_delete_revokes_the_refresh_token(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    uid = await _seed_user_with_provider(override_db_and_seed)
    refresh = create_refresh_token(user_id=uid, jti=str(uuid.uuid4()))

    resp = await client.request(
        "DELETE", "/v1/users/me", headers=_auth(uid), json={"refreshToken": refresh}
    )
    assert resp.status_code == 204

    again = await client.post("/v1/auth/refresh", json={"refreshToken": refresh})
    assert again.status_code == 401
    assert again.json()["error"]["code"] == "AUTH_SESSION_REVOKED"


@pytest.mark.asyncio
async def test_delete_without_auth_returns_401(client: AsyncClient) -> None:
    resp = await client.delete("/v1/users/me")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "AUTH_TOKEN_INVALID"
