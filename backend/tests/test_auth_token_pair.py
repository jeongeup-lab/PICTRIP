import json

import pytest

from app.core.auth import (
    create_refresh_token,
    decode_token,
    issue_token_pair,
    revoke_all_user_sessions,
    revoke_session,
    rotate_refresh,
)
from app.core.exceptions import AuthSessionRevoked, AuthTokenInvalid


@pytest.mark.asyncio
async def test_issue_token_pair_writes_all_redis_keys(redis_client_fake):
    pair = await issue_token_pair(redis_client_fake, user_id=42)

    refresh_payload = decode_token(pair.refreshToken)
    jti = refresh_payload["jti"]
    sid = refresh_payload["sid"]

    active_raw = await redis_client_fake.get(f"rt:active:{jti}")
    assert active_raw is not None
    active = json.loads(active_raw)
    assert active["uid"] == 42
    assert active["sid"] == sid

    members = await redis_client_fake.smembers(f"sess:{sid}")
    assert jti.encode() in members or jti in members

    z = await redis_client_fake.zrange("user:sessions:42", 0, -1)
    assert sid.encode() in z or sid in z


@pytest.mark.asyncio
async def test_issue_token_pair_cleans_expired_user_sessions(redis_client_fake):
    await redis_client_fake.zadd("user:sessions:42", {"old-sid": 1})
    await issue_token_pair(redis_client_fake, user_id=42)
    z = await redis_client_fake.zrange("user:sessions:42", 0, -1)
    assert b"old-sid" not in z and "old-sid" not in z


@pytest.mark.asyncio
async def test_rotate_refresh_happy_path(redis_client_fake):
    pair = await issue_token_pair(redis_client_fake, user_id=7)
    new_pair = await rotate_refresh(redis_client_fake, pair.refreshToken)
    assert new_pair.refreshToken != pair.refreshToken
    old_jti = decode_token(pair.refreshToken)["jti"]
    assert await redis_client_fake.get(f"rt:active:{old_jti}") is None
    assert await redis_client_fake.exists(f"rt:deny:{old_jti}") == 1


@pytest.mark.asyncio
async def test_rotate_refresh_grace_returns_same_pair(redis_client_fake):
    pair = await issue_token_pair(redis_client_fake, user_id=7)
    new_pair_1 = await rotate_refresh(redis_client_fake, pair.refreshToken)
    new_pair_2 = await rotate_refresh(redis_client_fake, pair.refreshToken)
    assert new_pair_2.refreshToken == new_pair_1.refreshToken
    assert new_pair_2.accessToken == new_pair_1.accessToken


@pytest.mark.asyncio
async def test_rotate_refresh_notfound_raises(redis_client_fake):
    fake = create_refresh_token(user_id=9, jti="ghost-jti", sid="ghost-sid")
    with pytest.raises(AuthTokenInvalid):
        await rotate_refresh(redis_client_fake, fake)


@pytest.mark.asyncio
async def test_rotate_refresh_detects_reuse_and_revokes_family(redis_client_fake):
    pair = await issue_token_pair(redis_client_fake, user_id=11)
    old_refresh = pair.refreshToken
    sid = decode_token(old_refresh)["sid"]

    new_pair = await rotate_refresh(redis_client_fake, old_refresh)

    # Force grace key gone (simulates time past the 5s window)
    old_jti = decode_token(old_refresh)["jti"]
    await redis_client_fake.delete(f"rt:grace:{old_jti}")

    with pytest.raises(AuthSessionRevoked):
        await rotate_refresh(redis_client_fake, old_refresh)

    # Family revoke wiped sess:{sid} entirely
    members = await redis_client_fake.smembers(f"sess:{sid}")
    assert members == set()
    # The new jti issued in the first rotate is also gone
    new_jti = decode_token(new_pair.refreshToken)["jti"]
    assert await redis_client_fake.exists(f"rt:active:{new_jti}") == 0
    # user:sessions index no longer carries this sid
    z = await redis_client_fake.zrange("user:sessions:11", 0, -1)
    assert sid.encode() not in z and sid not in z


@pytest.mark.asyncio
async def test_revoke_session_wipes_one_family(redis_client_fake):
    pair = await issue_token_pair(redis_client_fake, user_id=20)
    sid = decode_token(pair.refreshToken)["sid"]
    await revoke_session(redis_client_fake, uid=20, sid=sid)

    assert await redis_client_fake.exists(f"sess:{sid}") == 0
    jti = decode_token(pair.refreshToken)["jti"]
    assert await redis_client_fake.exists(f"rt:active:{jti}") == 0
    z = await redis_client_fake.zrange("user:sessions:20", 0, -1)
    assert sid.encode() not in z and sid not in z


@pytest.mark.asyncio
async def test_revoke_all_user_sessions_wipes_every_family(redis_client_fake):
    pair_a = await issue_token_pair(redis_client_fake, user_id=30)
    pair_b = await issue_token_pair(redis_client_fake, user_id=30)
    sid_a = decode_token(pair_a.refreshToken)["sid"]
    sid_b = decode_token(pair_b.refreshToken)["sid"]
    await revoke_all_user_sessions(redis_client_fake, uid=30)
    for sid in (sid_a, sid_b):
        assert await redis_client_fake.exists(f"sess:{sid}") == 0
    z = await redis_client_fake.zrange("user:sessions:30", 0, -1)
    assert z == []
