"""Integration + service tests for email/password auth.

Routes under test:
  POST /v1/auth/email/signup
  POST /v1/auth/email/login

Uses the same savepoint-isolated DB override + fakeredis pattern as
test_users_auth_routes.py so no real Redis is needed and rows never leak.
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.main import app
from app.modules.users.models import User, UserAuthProvider
from app.modules.users.schemas import EmailLoginIn, EmailSignupIn
from app.modules.users.services import login_with_email, signup_with_email


def _email() -> str:
    return f"u-{uuid.uuid4().hex[:10]}@example.com"


@pytest_asyncio.fixture(autouse=True)
async def override_db():
    from fakeredis.aioredis import FakeRedis

    from app.core.db import get_db
    from app.core.redis import get_redis

    # Fresh fakeredis per test so rate-limit counters never bleed across tests.
    fake = FakeRedis(decode_responses=True)
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
            app.dependency_overrides[get_redis] = lambda: fake
            yield
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_redis, None)
        finally:
            if tx.is_active:
                await tx.rollback()
    await eng.dispose()
    await fake.aclose()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


async def test_signup_returns_token_pair_and_sets_email(client):
    email = _email()
    resp = await client.post(
        "/v1/auth/email/signup",
        json={"email": email, "password": "hunter2pw", "name": "Nina"},
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["accessToken"]
    assert data["refreshToken"]
    assert data["user"]["email"] == email
    assert data["user"]["displayName"] == "Nina"


async def test_signup_duplicate_active_email_returns_409(client):
    email = _email()
    first = await client.post(
        "/v1/auth/email/signup", json={"email": email, "password": "hunter2pw"}
    )
    assert first.status_code == 201
    dup = await client.post("/v1/auth/email/signup", json={"email": email, "password": "anotherpw"})
    assert dup.status_code == 409
    assert dup.json()["error"]["code"] == "EMAIL_TAKEN"


async def test_signup_normalizes_email_case(client):
    email = _email()
    await client.post("/v1/auth/email/signup", json={"email": email, "password": "hunter2pw"})
    dup = await client.post(
        "/v1/auth/email/signup",
        json={"email": email.upper(), "password": "hunter2pw"},
    )
    assert dup.status_code == 409
    assert dup.json()["error"]["code"] == "EMAIL_TAKEN"


async def test_signup_short_password_returns_422(client):
    resp = await client.post("/v1/auth/email/signup", json={"email": _email(), "password": "short"})
    assert resp.status_code == 422


async def test_login_happy_path_returns_pair(client):
    email = _email()
    await client.post("/v1/auth/email/signup", json={"email": email, "password": "hunter2pw"})
    resp = await client.post("/v1/auth/email/login", json={"email": email, "password": "hunter2pw"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["accessToken"]
    assert data["user"]["email"] == email


async def test_login_wrong_password_returns_401(client):
    email = _email()
    await client.post("/v1/auth/email/signup", json={"email": email, "password": "hunter2pw"})
    resp = await client.post("/v1/auth/email/login", json={"email": email, "password": "wrongpass"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "AUTH_INVALID_CREDENTIALS"


async def test_login_unknown_email_returns_401(client):
    resp = await client.post(
        "/v1/auth/email/login", json={"email": _email(), "password": "whatever1"}
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "AUTH_INVALID_CREDENTIALS"


async def test_login_overlong_password_returns_422(client):
    # Capped at bcrypt's 72-byte limit so a huge string can't waste a hash.
    resp = await client.post("/v1/auth/email/login", json={"email": _email(), "password": "x" * 73})
    assert resp.status_code == 422


async def test_login_rate_limited_after_threshold(client):
    # 10/min/IP — the 11th attempt (over limit) is throttled regardless of creds,
    # blunting brute-force / credential-stuffing from a single source.
    body = {"email": _email(), "password": "whatever1"}
    statuses = [
        (await client.post("/v1/auth/email/login", json=body)).status_code for _ in range(11)
    ]
    assert statuses[:10] == [401] * 10  # under the limit: handler runs (unknown email)
    assert statuses[10] == 429
    assert (await client.post("/v1/auth/email/login", json=body)).json()["error"][
        "code"
    ] == "RATE_LIMITED"


async def test_signup_rate_limited_after_threshold(client):
    # 5/min/IP — the 6th signup (over limit) is throttled, capping email
    # enumeration / spam account creation from a single source.
    statuses = [
        (
            await client.post(
                "/v1/auth/email/signup", json={"email": _email(), "password": "hunter2pw"}
            )
        ).status_code
        for _ in range(6)
    ]
    assert statuses[:5] == [201] * 5
    assert statuses[5] == 429


# ---------------------------------------------------------------------------
# Service layer
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_signup_stores_hashed_password_not_plaintext(db_session: AsyncSession) -> None:
    email = _email()
    await signup_with_email(db_session, EmailSignupIn(email=email, password="hunter2pw", name="H"))
    user = (await db_session.scalars(select(User).where(User.email == email))).one()
    assert user.password_hash is not None
    assert user.password_hash != "hunter2pw"
    assert user.password_hash.startswith("$2")
    provider = (
        await db_session.scalars(
            select(UserAuthProvider).where(UserAuthProvider.user_id == user.id)
        )
    ).one()
    assert provider.provider == "email"
    assert provider.provider_user_id == email


@pytest.mark.asyncio
async def test_login_with_email_verifies_password(db_session: AsyncSession) -> None:
    email = _email()
    await signup_with_email(db_session, EmailSignupIn(email=email, password="hunter2pw"))
    pair = await login_with_email(db_session, EmailLoginIn(email=email, password="hunter2pw"))
    assert pair.user.email == email
