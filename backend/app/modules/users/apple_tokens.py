from __future__ import annotations

import logging
import time

import httpx
import jwt

from app.config import settings

log = logging.getLogger("app.auth.apple")

_TIMEOUT = httpx.Timeout(connect=2.0, read=5.0, write=2.0, pool=2.0)
_CLIENT_SECRET_TTL_SECONDS = 15 * 60


def is_configured() -> bool:
    return bool(
        settings.APPLE_TEAM_ID
        and settings.APPLE_KEY_ID
        and settings.APPLE_PRIVATE_KEY
        and settings.APPLE_BUNDLE_ID
    )


def _private_key_pem() -> str:
    return settings.APPLE_PRIVATE_KEY.replace("\\n", "\n")


def build_client_secret() -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "iss": settings.APPLE_TEAM_ID,
            "iat": now,
            "exp": now + _CLIENT_SECRET_TTL_SECONDS,
            "aud": settings.APPLE_OIDC_ISSUER,
            "sub": settings.APPLE_BUNDLE_ID,
        },
        _private_key_pem(),
        algorithm="ES256",
        headers={"kid": settings.APPLE_KEY_ID},
    )


async def _post(url: str, data: dict[str, str]) -> httpx.Response:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        return await client.post(
            url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"}
        )


async def exchange_authorization_code(code: str) -> str | None:
    if not is_configured():
        log.warning("apple: token exchange skipped — key not configured")
        return None
    try:
        resp = await _post(
            settings.APPLE_TOKEN_URL,
            {
                "client_id": settings.APPLE_BUNDLE_ID or "",
                "client_secret": build_client_secret(),
                "code": code,
                "grant_type": "authorization_code",
            },
        )
    except httpx.HTTPError as exc:
        log.warning("apple: token exchange transport error (%s)", type(exc).__name__)
        return None
    if resp.status_code != 200:
        log.warning("apple: token exchange rejected (status=%s)", resp.status_code)
        return None
    token = resp.json().get("refresh_token")
    return str(token) if token else None


async def revoke_refresh_token(refresh_token: str) -> bool:
    if not is_configured():
        log.warning("apple: revoke skipped — key not configured")
        return False
    try:
        resp = await _post(
            settings.APPLE_REVOKE_URL,
            {
                "client_id": settings.APPLE_BUNDLE_ID or "",
                "client_secret": build_client_secret(),
                "token": refresh_token,
                "token_type_hint": "refresh_token",
            },
        )
    except httpx.HTTPError as exc:
        log.warning("apple: revoke transport error (%s)", type(exc).__name__)
        return False
    if resp.status_code != 200:
        log.warning("apple: revoke rejected (status=%s)", resp.status_code)
        return False
    return True
