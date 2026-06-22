"""Denylist auth model (S08): issuance writes nothing to Redis; refresh is a
sliding re-mint with the SAME jti; logout adds denyjti; refresh fails open when
Redis is unavailable."""

from __future__ import annotations

import pytest

from app.core.auth import decode_token, deny_refresh, mint_token_pair, refresh_tokens
from app.core.exceptions import AuthSessionRevoked


async def test_mint_writes_nothing_to_redis(redis_client_fake):
    pair = mint_token_pair(user_id=42)
    assert pair.accessToken and pair.refreshToken
    assert await redis_client_fake.dbsize() == 0  # issuance = zero Redis writes


async def test_refresh_remints_same_jti_with_new_access(redis_client_fake):
    pair = mint_token_pair(user_id=42)
    old_jti = decode_token(pair.refreshToken)["jti"]
    new = await refresh_tokens(redis_client_fake, pair.refreshToken)
    assert decode_token(new.refreshToken)["jti"] == old_jti  # NOT rotated
    assert new.accessToken


async def test_denied_refresh_is_rejected(redis_client_fake):
    pair = mint_token_pair(user_id=42)
    await deny_refresh(redis_client_fake, pair.refreshToken)  # logout
    with pytest.raises(AuthSessionRevoked):
        await refresh_tokens(redis_client_fake, pair.refreshToken)


async def test_refresh_fails_open_when_redis_unavailable(monkeypatch, redis_client_fake):
    pair = mint_token_pair(user_id=42)

    async def boom(*a, **k):
        raise ConnectionError("redis down")

    monkeypatch.setattr(redis_client_fake, "exists", boom)
    new = await refresh_tokens(redis_client_fake, pair.refreshToken)  # passes (fail-open)
    assert new.accessToken


async def test_deny_refresh_is_idempotent_and_ignores_bad_tokens(redis_client_fake):
    # None / malformed tokens are silent no-ops.
    await deny_refresh(redis_client_fake, None)
    await deny_refresh(redis_client_fake, "not.a.jwt")
    assert await redis_client_fake.dbsize() == 0


async def test_deny_refresh_swallows_redis_write_failure(monkeypatch, redis_client_fake):
    pair = mint_token_pair(user_id=42)

    async def boom(*a, **k):
        raise ConnectionError("redis down")

    monkeypatch.setattr(redis_client_fake, "set", boom)
    await deny_refresh(redis_client_fake, pair.refreshToken)  # does not raise
