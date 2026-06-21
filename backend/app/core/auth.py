"""JWT issuance, verification, and FastAPI dependencies.

RS256 with key material loaded from settings (Secrets Manager in prod).
For local dev with empty keys, a dev fallback HS256 secret is used.

Uses PyJWT (with `cryptography` backend) rather than python-jose because the
latter transitively pulls in `python-ecdsa`, which has an unfixed Minerva
timing attack on P-256 (CVE-2024-23342). See docs/adr/0005 if we need to
revisit JWT lib choice.
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Annotated, Any

import jwt
from fastapi import Depends, Header
from jwt import ExpiredSignatureError, InvalidTokenError
from redis.asyncio import Redis

from app.config import settings
from app.core.exceptions import (
    AuthSessionRevoked,
    AuthTokenExpired,
    AuthTokenInvalid,
    SessionStoreUnavailable,  # noqa: F401 — reserved for Task 10 (Redis error handling)
)

if TYPE_CHECKING:
    from app.modules.users.schemas import TokenPair, UserPublic

# `users.schemas` is imported lazily inside the functions that mint a TokenPair to
# avoid an import cycle: a module whose package sorts before `usr` (e.g. `sys`)
# loads `app.core.auth` first, and an eager top-level `usr` import here would
# re-enter `users.routes` -> `app.core.auth` before this module finished loading.

_DEV_HS256_SECRET = "pictrip-local-dev-only-not-for-prod"


def _signing_key() -> tuple[str, str]:
    """Return (key, algorithm). RS256 in prod, HS256 fallback in local without keys."""
    if settings.JWT_PRIVATE_KEY and settings.JWT_PUBLIC_KEY:
        return settings.JWT_PRIVATE_KEY, settings.JWT_ALGORITHM
    if settings.is_production:
        raise RuntimeError("JWT_PRIVATE_KEY / JWT_PUBLIC_KEY must be set in production.")
    return _DEV_HS256_SECRET, "HS256"


def _verify_key() -> tuple[str, str]:
    if settings.JWT_PUBLIC_KEY:
        return settings.JWT_PUBLIC_KEY, settings.JWT_ALGORITHM
    if settings.is_production:
        raise RuntimeError("JWT_PUBLIC_KEY must be set in production.")
    return _DEV_HS256_SECRET, "HS256"


def create_access_token(*, user_id: int, extra_claims: dict[str, Any] | None = None) -> str:
    key, algo = _signing_key()
    now = datetime.now(tz=UTC)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=settings.JWT_ACCESS_TOKEN_TTL_SECONDS)).timestamp()),
        "type": "access",
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, key, algorithm=algo)


def create_refresh_token(*, user_id: int, jti: str, sid: str) -> str:
    key, algo = _signing_key()
    now = datetime.now(tz=UTC)
    payload = {
        "sub": str(user_id),
        "jti": jti,
        "sid": sid,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=settings.JWT_REFRESH_TOKEN_TTL_SECONDS)).timestamp()),
        "type": "refresh",
    }
    return jwt.encode(payload, key, algorithm=algo)


def decode_token(token: str) -> dict[str, Any]:
    key, algo = _verify_key()
    try:
        decoded: dict[str, Any] = jwt.decode(token, key, algorithms=[algo])
    except ExpiredSignatureError as e:
        raise AuthTokenExpired() from e
    except InvalidTokenError as e:
        raise AuthTokenInvalid() from e
    return decoded


async def get_current_user_id(
    authorization: Annotated[str | None, Header()] = None,
) -> int:
    """FastAPI dependency: extract user_id from Bearer token."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AuthTokenInvalid()
    token = authorization.split(" ", 1)[1].strip()
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise AuthTokenInvalid()
    try:
        return int(payload["sub"])
    except (KeyError, TypeError, ValueError) as e:
        raise AuthTokenInvalid() from e


CurrentUserId = Annotated[int, Depends(get_current_user_id)]


async def issue_token_pair(
    redis: Redis,
    *,
    user_id: int,
    user: UserPublic | None = None,
    sid: str | None = None,
) -> TokenPair:
    """Mint a new access/refresh pair and write the Redis session family."""
    from app.modules.users.schemas import TokenPair, UserPublic

    sid = sid or str(uuid.uuid4())
    jti = str(uuid.uuid4())
    refresh_ttl = settings.JWT_REFRESH_TOKEN_TTL_SECONDS
    access_ttl = settings.JWT_ACCESS_TOKEN_TTL_SECONDS

    access = create_access_token(user_id=user_id)
    refresh = create_refresh_token(user_id=user_id, jti=jti, sid=sid)

    now = int(time.time())
    exp_unix = now + refresh_ttl
    payload = json.dumps({"uid": user_id, "sid": sid, "exp": exp_unix})

    pipe = redis.pipeline()
    pipe.set(f"rt:active:{jti}", payload, ex=refresh_ttl)
    pipe.sadd(f"sess:{sid}", jti)
    pipe.expire(f"sess:{sid}", refresh_ttl)
    pipe.zremrangebyscore(f"user:sessions:{user_id}", 0, now)
    pipe.zadd(f"user:sessions:{user_id}", {sid: exp_unix})
    await pipe.execute()

    return TokenPair(
        accessToken=access,
        refreshToken=refresh,
        expiresIn=access_ttl,
        user=user or UserPublic(id=user_id, isOnboarded=False),
    )


# GRACE is checked before DENY so that concurrent retries within the 5 s window
# get the cached pair rather than hitting the family-revoke path.
# After the grace TTL expires, only the deny marker remains → REUSE fires.
ROTATE_LUA = """
local stored = redis.call('GETDEL', KEYS[1])
if stored == false then
  local g = redis.call('GET', KEYS[3])
  if g then return {'GRACE', g} end
  if redis.call('EXISTS', KEYS[2]) == 1 then return {'REUSE'} end
  return {'NOTFOUND'}
end
redis.call('SET', KEYS[2], 1, 'EX', ARGV[1])
redis.call('SET', KEYS[5], ARGV[4], 'EX', ARGV[1])
redis.call('SADD', KEYS[4], ARGV[3])
redis.call('EXPIRE', KEYS[4], ARGV[1])
redis.call('SET', KEYS[3], ARGV[5], 'EX', ARGV[2])
return {'OK', stored}
"""


async def rotate_refresh(redis: Redis, refresh_token: str) -> TokenPair:
    """Rotate one refresh token. Raises AuthTokenInvalid / AuthSessionRevoked / AuthTokenExpired.

    REUSE detection currently raises AuthTokenInvalid — Task 9 will wire family-revoke
    and raise AuthSessionRevoked instead.
    """
    from app.modules.users.schemas import TokenPair, UserPublic

    payload = decode_token(refresh_token)
    if payload.get("type") != "refresh":
        raise AuthTokenInvalid()
    uid = int(payload["sub"])
    old_jti = payload["jti"]
    sid = payload["sid"]

    new_jti = str(uuid.uuid4())
    refresh_ttl = settings.JWT_REFRESH_TOKEN_TTL_SECONDS
    access_ttl = settings.JWT_ACCESS_TOKEN_TTL_SECONDS
    grace_ttl = settings.AUTH_REFRESH_GRACE_SECONDS

    now = int(time.time())
    exp_unix = now + refresh_ttl
    new_active_payload = json.dumps({"uid": uid, "sid": sid, "exp": exp_unix})

    new_access = create_access_token(user_id=uid)
    new_refresh = create_refresh_token(user_id=uid, jti=new_jti, sid=sid)
    new_pair = TokenPair(
        accessToken=new_access,
        refreshToken=new_refresh,
        expiresIn=access_ttl,
        user=UserPublic(id=uid, isOnboarded=False),
    )
    new_pair_json = new_pair.model_dump_json()

    raw_result: Any = await redis.eval(  # type: ignore[misc]
        ROTATE_LUA,
        5,
        f"rt:active:{old_jti}",
        f"rt:deny:{old_jti}",
        f"rt:grace:{old_jti}",
        f"sess:{sid}",
        f"rt:active:{new_jti}",
        str(refresh_ttl),
        str(grace_ttl),
        new_jti,
        new_active_payload,
        new_pair_json,
    )
    result: list[Any] = raw_result

    tag: Any = result[0]
    if isinstance(tag, bytes):
        tag = tag.decode()

    if tag == "OK":
        return new_pair
    if tag == "GRACE":
        cached = result[1]
        if isinstance(cached, bytes):
            cached = cached.decode()
        return TokenPair.model_validate_json(cached)
    if tag == "REUSE":
        await _revoke_family(redis, uid=uid, sid=sid)
        raise AuthSessionRevoked()
    # NOTFOUND
    raise AuthTokenInvalid()


async def _revoke_family(redis: Redis, *, uid: int, sid: str) -> None:
    """Delete every refresh tied to a sid + drop the sid from the user index."""
    members = await redis.smembers(f"sess:{sid}")  # type: ignore[misc]
    keys_to_del = [f"rt:active:{m.decode() if isinstance(m, bytes) else m}" for m in members]
    keys_to_del.append(f"sess:{sid}")
    pipe = redis.pipeline()
    if keys_to_del:
        pipe.delete(*keys_to_del)
    pipe.zrem(f"user:sessions:{uid}", sid)
    await pipe.execute()


async def revoke_session(redis: Redis, *, uid: int, sid: str) -> None:
    """Public entry point for the logout path; same effect as _revoke_family."""
    await _revoke_family(redis, uid=uid, sid=sid)


async def revoke_all_user_sessions(redis: Redis, *, uid: int) -> None:
    """Wipe every active session for a user (e.g. account compromise response)."""
    sids = await redis.zrange(f"user:sessions:{uid}", 0, -1)
    decoded = [s.decode() if isinstance(s, bytes) else s for s in sids]
    for sid in decoded:
        await _revoke_family(redis, uid=uid, sid=sid)
