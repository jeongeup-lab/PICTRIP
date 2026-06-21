"""Security regression suite — five load-bearing cases per design §5.4.

Marked @pytest.mark.real_redis so CI can isolate these into a job with Docker.
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import jwt
import pytest

from app.core.auth import decode_token, rotate_refresh
from app.core.exceptions import AuthSessionRevoked, AuthTokenInvalid
from app.core.kakao_oidc import KakaoClaims
from app.modules.users.schemas import KakaoCallbackIn
from app.modules.users.services import authenticate_with_kakao

pytestmark = pytest.mark.real_redis


@pytest.fixture
def fake_claims():
    return KakaoClaims(
        sub=f"sec-{uuid4().hex}",
        email=None,
        nickname=None,
        picture=None,
        nonce=None,
    )


@pytest.fixture(autouse=True)
async def override_db():
    """Per-test savepoint-isolated session to avoid row leakage.

    A single connection per test is wrapped in an outer transaction that is
    always rolled back at teardown.  The inner ``AsyncSession`` uses
    ``join_transaction_mode="create_savepoint"`` so service-level
    ``session.commit()`` calls become savepoints rather than real COMMITs,
    keeping the DB clean for subsequent tests.
    """
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.pool import NullPool

    from app.config import settings
    from app.core.db import get_db
    from app.main import app

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


async def _login(db_session, redis_real, fake_claims):
    with patch(
        "app.modules.users.services.verify_id_token",
        AsyncMock(return_value=fake_claims),
    ):
        return await authenticate_with_kakao(db_session, redis_real, KakaoCallbackIn(idToken="x"))


@pytest.mark.asyncio
async def test_refresh_replay_revokes_family(db_session, redis_client_real, fake_claims):
    pair = await _login(db_session, redis_client_real, fake_claims)
    new_pair = await rotate_refresh(redis_client_real, pair.refreshToken)

    # Drop the grace key so the replay lands on REUSE (not GRACE).
    old_jti = decode_token(pair.refreshToken)["jti"]
    await redis_client_real.delete(f"rt:grace:{old_jti}")

    with pytest.raises(AuthSessionRevoked):
        await rotate_refresh(redis_client_real, pair.refreshToken)

    sid = decode_token(pair.refreshToken)["sid"]
    # sess:{sid} wiped
    assert await redis_client_real.exists(f"sess:{sid}") == 0
    # the new jti from the legitimate rotate is also gone
    new_jti = decode_token(new_pair.refreshToken)["jti"]
    assert await redis_client_real.exists(f"rt:active:{new_jti}") == 0
    # access JWTs issued before revoke are NOT invalidated (15-min stateless boundary)
    # — this is documented design §2.4. No assertion here; just noted.


@pytest.mark.asyncio
async def test_cross_account_signature_rejected(redis_client_real):
    """Refresh JWT forged with wrong HS256 secret must be rejected at decode."""
    forged = jwt.encode(
        {
            "sub": "999",
            "jti": "x",
            "sid": "y",
            "type": "refresh",
            "exp": int(time.time()) + 600,
            "iat": int(time.time()),
        },
        "wrong-secret",
        algorithm="HS256",
    )
    with pytest.raises(AuthTokenInvalid):
        await rotate_refresh(redis_client_real, forged)


@pytest.mark.asyncio
async def test_token_type_confusion_blocked(client, db_session, redis_client_real, fake_claims):
    """Refresh JWT sent in Authorization header for /users/me must be rejected."""
    from app.core.redis import get_redis
    from app.main import app

    app.dependency_overrides[get_redis] = lambda: redis_client_real
    try:
        pair = await _login(db_session, redis_client_real, fake_claims)
        # Send the refresh JWT as a Bearer access token
        resp = await client.get(
            "/v1/users/me",
            headers={"Authorization": f"Bearer {pair.refreshToken}"},
        )
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "AUTH_TOKEN_INVALID"
    finally:
        app.dependency_overrides.pop(get_redis, None)


@pytest.mark.asyncio
async def test_id_token_aud_spoof_rejected(
    client, kakao_signing_key, mock_kakao_jwks, monkeypatch, redis_client_real
):
    """Real verify_id_token path — a Kakao-signed token with wrong aud must 401."""
    from app.core.redis import get_redis
    from app.main import app
    from tests.conftest import make_kakao_id_token

    app.dependency_overrides[get_redis] = lambda: redis_client_real
    try:
        monkeypatch.setattr("app.config.settings.KAKAO_REST_API_KEY", "real-aud")
        priv, _ = kakao_signing_key
        bad = make_kakao_id_token(sub="aud-spoof", aud="wrong-aud", key=priv)
        resp = await client.post("/v1/auth/oauth/kakao", json={"idToken": bad})
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "OAUTH_ID_TOKEN_INVALID"
    finally:
        app.dependency_overrides.pop(get_redis, None)


@pytest.mark.asyncio
async def test_concurrent_rotation_converges(db_session, redis_client_real, fake_claims):
    """asyncio.gather(rotate x 5) returns the SAME new pair every time (one OK + four GRACE)."""
    pair = await _login(db_session, redis_client_real, fake_claims)
    results = await asyncio.gather(
        *[rotate_refresh(redis_client_real, pair.refreshToken) for _ in range(5)]
    )
    refresh_tokens = {r.refreshToken for r in results}
    assert len(refresh_tokens) == 1
