"""Pytest fixtures for async FastAPI + SQLAlchemy."""

from __future__ import annotations

import time
from base64 import urlsafe_b64encode
from collections.abc import AsyncGenerator

import jwt
import pytest
import pytest_asyncio
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fakeredis.aioredis import FakeRedis
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.main import app


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Function-scoped session wrapped in an outer transaction that is always
    rolled back, so DB-touching tests stay isolated even when they hit
    triggers or constraint violations.

    A fresh engine with NullPool is created per test because pytest-asyncio's
    default function-scoped event loop makes the module-level `app.core.db.engine`
    unsafe to share across tests."""
    eng = create_async_engine(settings.sqlalchemy_database_url, poolclass=NullPool)
    try:
        async with eng.connect() as conn:
            tx = await conn.begin()
            session = AsyncSession(
                bind=conn,
                expire_on_commit=False,
                join_transaction_mode="create_savepoint",
            )
            try:
                yield session
            finally:
                await session.close()
                if tx.is_active:
                    await tx.rollback()
    finally:
        await eng.dispose()


@pytest_asyncio.fixture
async def redis_client_fake() -> AsyncGenerator[FakeRedis, None]:
    """In-memory async Redis for unit tests. Single connection per test."""
    client = FakeRedis(decode_responses=False)
    try:
        yield client
    finally:
        await client.aclose()


@pytest_asyncio.fixture
async def redis_client_real():
    """Real Redis 7 via testcontainers. Skipped if Docker is unavailable."""
    pytest_docker = pytest.importorskip("testcontainers.redis", reason="testcontainers required")
    from redis.asyncio import from_url

    container = pytest_docker.RedisContainer("redis:7-alpine")
    try:
        container.start()
    except Exception as exc:
        pytest.skip(f"Docker unavailable: {exc}")
    try:
        url = f"redis://{container.get_container_host_ip()}:{container.get_exposed_port(6379)}"
        client = from_url(url, decode_responses=False)
        try:
            yield client
        finally:
            await client.aclose()
    finally:
        container.stop()


def _b64url_uint(n: int) -> str:
    raw = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return urlsafe_b64encode(raw).rstrip(b"=").decode()


@pytest.fixture(scope="session")
def kakao_signing_key() -> tuple[rsa.RSAPrivateKey, dict]:
    """RSA-2048 keypair + JWKS dict (single key with kid='test-kid-1')."""
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub = private.public_key().public_numbers()
    jwks = {
        "keys": [
            {
                "kty": "RSA",
                "alg": "RS256",
                "use": "sig",
                "kid": "test-kid-1",
                "n": _b64url_uint(pub.n),
                "e": _b64url_uint(pub.e),
            }
        ]
    }
    return private, jwks


@pytest.fixture
def mock_kakao_jwks(httpx_mock, kakao_signing_key):
    """Default JWKS HTTP response. Tests can override via httpx_mock."""
    _, jwks = kakao_signing_key
    httpx_mock.add_response(
        url="https://kauth.kakao.com/.well-known/jwks.json",
        json=jwks,
    )
    yield httpx_mock


def make_kakao_id_token(
    *,
    sub: str,
    aud: str = "test-rest-api-key",
    iss: str = "https://kauth.kakao.com",
    exp_offset: int = 600,
    iat_offset: int = 0,
    nonce: str | None = None,
    key,
    kid: str = "test-kid-1",
    extra: dict | None = None,
) -> str:
    now = int(time.time())
    payload = {
        "iss": iss,
        "aud": aud,
        "sub": sub,
        "iat": now + iat_offset,
        "exp": now + exp_offset,
    }
    if nonce is not None:
        payload["nonce"] = nonce
    if extra:
        payload.update(extra)
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return jwt.encode(payload, pem, algorithm="RS256", headers={"kid": kid})
