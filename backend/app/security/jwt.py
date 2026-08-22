from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Annotated, Any

import jwt
from fastapi import Depends, Header
from jwt import ExpiredSignatureError, InvalidTokenError
from redis.asyncio import Redis

from app.config import settings
from app.core.logging import get_logger
from app.web.errors import (
    AuthSessionRevoked,
    AuthTokenExpired,
    AuthTokenInvalid,
)

logger = get_logger(__name__)

if TYPE_CHECKING:
    from app.modules.users.schemas import TokenPair, UserPublic


_DEV_HS256_SECRET = "pictrip-local-dev-only-not-for-prod"


def _signing_key() -> tuple[str, str]:
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


def create_refresh_token(*, user_id: int, jti: str) -> str:
    key, algo = _signing_key()
    now = datetime.now(tz=UTC)
    payload = {
        "sub": str(user_id),
        "jti": jti,
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


async def get_optional_user_id(
    authorization: Annotated[str | None, Header()] = None,
) -> int | None:
    """익명으로도 도는 화면용. 만료 토큰이 검색을 죽이면 안 된다."""
    try:
        return await get_current_user_id(authorization)
    except (AuthTokenInvalid, AuthTokenExpired):
        return None


OptionalUserId = Annotated[int | None, Depends(get_optional_user_id)]


def mint_token_pair(*, user_id: int, user: UserPublic | None = None) -> TokenPair:
    from app.modules.users.schemas import TokenPair, UserPublic

    access = create_access_token(user_id=user_id)
    refresh = create_refresh_token(user_id=user_id, jti=str(uuid.uuid4()))
    return TokenPair(
        accessToken=access,
        refreshToken=refresh,
        expiresIn=settings.JWT_ACCESS_TOKEN_TTL_SECONDS,
        user=user or UserPublic(id=user_id, isOnboarded=False),
    )


async def refresh_tokens(redis: Redis, refresh_token: str) -> TokenPair:
    from app.modules.users.schemas import TokenPair, UserPublic

    payload = decode_token(refresh_token)
    if payload.get("type") != "refresh":
        raise AuthTokenInvalid()
    jti = payload.get("jti")
    if not jti:
        raise AuthTokenInvalid()
    try:
        denied = await redis.exists(f"denyjti:{jti}")
    except Exception:
        logger.warning("denylist_check_failed_fail_open", jti=jti)
        denied = 0
    if denied:
        raise AuthSessionRevoked()

    uid = int(payload["sub"])
    access = create_access_token(user_id=uid)
    refresh = create_refresh_token(user_id=uid, jti=jti)
    return TokenPair(
        accessToken=access,
        refreshToken=refresh,
        expiresIn=settings.JWT_ACCESS_TOKEN_TTL_SECONDS,
        user=UserPublic(id=uid, isOnboarded=False),
    )


async def deny_refresh(redis: Redis, refresh_token: str | None) -> None:
    if not refresh_token:
        return
    try:
        payload = decode_token(refresh_token)
    except (AuthTokenInvalid, AuthTokenExpired):
        return
    jti = payload.get("jti")
    if payload.get("type") != "refresh" or not jti:
        return
    ttl = max(1, int(payload["exp"]) - int(time.time()))
    try:
        await redis.set(f"denyjti:{jti}", "1", ex=ttl)
    except Exception:
        logger.warning("denylist_write_failed", jti=jti)
