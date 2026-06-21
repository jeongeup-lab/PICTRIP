"""Kakao OIDC verification — JWKS cache + id_token verification.

Network policy (per design §4.5):
- timeouts: 2s connect, 3s read
- JWKS fetch retries once on failure
- JWKS held for 1h fresh; up to 24h stale-on-error
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from app.config import settings
from app.core.exceptions import OAuthProviderUnavailable

_JWKS_TIMEOUT = httpx.Timeout(connect=2.0, read=3.0, write=2.0, pool=2.0)

# Module-level cache. Keys:
#   "value"        -> JWKS dict
#   "fresh_until"  -> int unix ts; before this, return cached without refetch
#   "stale_until"  -> int unix ts; up to this, return stale on error
_jwks_cache: dict[str, Any] = {}


async def _fetch_jwks() -> dict[str, Any]:
    """One-shot fetch with a single retry."""
    last_exc: Exception | None = None
    async with httpx.AsyncClient(timeout=_JWKS_TIMEOUT) as client:
        for _ in range(2):
            try:
                resp = await client.get(settings.KAKAO_JWKS_URL)
                resp.raise_for_status()
                data: dict[str, Any] = resp.json()
                return data
            except Exception as exc:  # surface any transport/HTTP error uniformly
                last_exc = exc
                continue
    raise OAuthProviderUnavailable() from last_exc


async def get_jwks() -> dict[str, Any]:
    """Return a cached JWKS, refreshing or serving stale-on-error per policy."""
    now = int(time.time())
    if _jwks_cache and now < _jwks_cache.get("fresh_until", 0):
        return _jwks_cache["value"]  # type: ignore[no-any-return]

    try:
        jwks = await _fetch_jwks()
    except OAuthProviderUnavailable:
        if _jwks_cache and now < _jwks_cache.get("stale_until", 0):
            return _jwks_cache["value"]  # type: ignore[no-any-return]
        raise

    _jwks_cache["value"] = jwks
    _jwks_cache["fresh_until"] = now + settings.KAKAO_JWKS_CACHE_TTL_SECONDS
    _jwks_cache["stale_until"] = now + settings.KAKAO_JWKS_STALE_ON_ERROR_TTL_SECONDS
    return jwks


# ---------------------------------------------------------------------------
# KakaoClaims + verify_id_token
# ---------------------------------------------------------------------------

from dataclasses import dataclass  # noqa: E402

import jwt  # noqa: E402


@dataclass(frozen=True)
class KakaoClaims:
    sub: str
    email: str | None
    nickname: str | None
    picture: str | None
    nonce: str | None


def _jwk_to_pem(jwk: dict[str, Any]) -> bytes:
    """Convert a single RSA JWK dict into PEM bytes for PyJWT verification."""
    from base64 import urlsafe_b64decode

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicNumbers

    def _b64u_to_int(s: str) -> int:
        pad = "=" * (-len(s) % 4)
        return int.from_bytes(urlsafe_b64decode(s + pad), "big")

    pub = RSAPublicNumbers(e=_b64u_to_int(jwk["e"]), n=_b64u_to_int(jwk["n"]))
    return pub.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )


async def verify_id_token(token: str, *, expected_nonce: str | None = None) -> KakaoClaims:
    """Verify a Kakao OIDC id_token. Raises OAuthIdTokenInvalid / OAuthProviderUnavailable.

    On the failure path each branch logs the exception class only — no token
    contents — so 401 root-causes are diagnosable without leaking PII (sub,
    aud, etc) into the structured-log backend.
    """
    import logging

    from app.core.exceptions import OAuthIdTokenInvalid

    log = logging.getLogger("app.auth.oidc")

    try:
        header = jwt.get_unverified_header(token)
    except jwt.InvalidTokenError as exc:
        log.info("verify_id_token: malformed header (%s)", type(exc).__name__)
        raise OAuthIdTokenInvalid() from exc
    kid = header.get("kid")
    if not kid:
        log.info("verify_id_token: missing kid")
        raise OAuthIdTokenInvalid()

    jwks = await get_jwks()
    matching = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)
    if matching is None:
        log.info("verify_id_token: kid not in JWKS")
        raise OAuthIdTokenInvalid()

    # `aud` can be either the REST API key (web/server flow) or the Native App
    # Key (mobile SDK flow) depending on which key the client used at OAuth init.
    valid_audiences = [a for a in (settings.KAKAO_REST_API_KEY, settings.KAKAO_NATIVE_APP_KEY) if a]
    pem = _jwk_to_pem(matching)
    try:
        payload = jwt.decode(
            token,
            pem,
            algorithms=["RS256"],
            audience=valid_audiences or None,
            issuer=settings.KAKAO_OIDC_ISSUER,
            leeway=300,  # spec §1.2 allows ±5 min skew
        )
    except jwt.InvalidTokenError as exc:
        log.info("verify_id_token: jwt.decode rejected (%s)", type(exc).__name__)
        raise OAuthIdTokenInvalid() from exc

    if expected_nonce is not None and payload.get("nonce") != expected_nonce:
        log.info("verify_id_token: nonce mismatch")
        raise OAuthIdTokenInvalid()

    return KakaoClaims(
        sub=str(payload["sub"]),
        email=payload.get("email"),
        nickname=payload.get("nickname"),
        picture=payload.get("picture"),
        nonce=payload.get("nonce"),
    )
