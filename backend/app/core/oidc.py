"""Provider-agnostic OIDC id_token verification (kakao / google / apple).

Kakao delegates to the existing `app.core.kakao_oidc` path. Google and Apple use
a generic verifier that fetches the provider JWKS (1h fresh / 24h stale-on-error,
same policy as Kakao), matches the `kid`, and verifies signature + iss + aud +
exp, rejecting `alg:none`. Apple additionally checks the hashed nonce.

Per S09 §3.1 the user identity key is `provider + sub`. On the failure path each
branch logs the exception class only — never token contents — so 401 root-causes
are diagnosable without leaking PII.
"""

from __future__ import annotations

import hashlib
import logging
import time
from base64 import urlsafe_b64encode
from dataclasses import dataclass
from typing import Any

import httpx
import jwt

from app.config import settings
from app.core.exceptions import (
    OAuthIdTokenInvalid,
    OAuthProviderUnavailable,
    ValidationFailed,
)
from app.core.kakao_oidc import verify_id_token as _verify_kakao

log = logging.getLogger("app.auth.oidc")

_JWKS_TIMEOUT = httpx.Timeout(connect=2.0, read=3.0, write=2.0, pool=2.0)

# Per-provider JWKS cache: provider -> {"value", "fresh_until", "stale_until"}.
_jwks_caches: dict[str, dict[str, Any]] = {}


@dataclass(frozen=True)
class OidcClaims:
    sub: str
    email: str | None
    name: str | None
    picture: str | None


async def _fetch_jwks(url: str) -> dict[str, Any]:
    """One-shot fetch with a single retry."""
    last_exc: Exception | None = None
    async with httpx.AsyncClient(timeout=_JWKS_TIMEOUT) as client:
        for _ in range(2):
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                data: dict[str, Any] = resp.json()
                return data
            except Exception as exc:  # surface any transport/HTTP error uniformly
                last_exc = exc
                continue
    raise OAuthProviderUnavailable() from last_exc


async def _get_jwks(provider: str, url: str) -> dict[str, Any]:
    """Cached JWKS per provider, refreshing or serving stale-on-error per policy."""
    now = int(time.time())
    cache = _jwks_caches.setdefault(provider, {})
    if cache and now < cache.get("fresh_until", 0):
        return cache["value"]  # type: ignore[no-any-return]
    try:
        jwks = await _fetch_jwks(url)
    except OAuthProviderUnavailable:
        if cache and now < cache.get("stale_until", 0):
            return cache["value"]  # type: ignore[no-any-return]
        raise
    cache["value"] = jwks
    cache["fresh_until"] = now + settings.KAKAO_JWKS_CACHE_TTL_SECONDS
    cache["stale_until"] = now + settings.KAKAO_JWKS_STALE_ON_ERROR_TTL_SECONDS
    return jwks


def _hashed_nonce(raw: str) -> str:
    """Apple stores nonce as base64url(sha256(raw)), no padding."""
    return urlsafe_b64encode(hashlib.sha256(raw.encode()).digest()).rstrip(b"=").decode()


async def _verify_generic(
    *,
    provider: str,
    url: str,
    issuers: list[str],
    audiences: list[str],
    algorithms: list[str],
    id_token: str,
    expected_nonce: str | None,
    hash_nonce: bool,
) -> OidcClaims:
    # An empty `audiences` list would make PyJWT SKIP `aud` validation entirely
    # (jwt.decode(audience=None)), so any validly-signed token from ANY OAuth
    # client of this provider would be accepted — a token-substitution /
    # account-takeover hole. A provider with no configured audience is therefore
    # treated as misconfigured/disabled and fails loudly rather than silently.
    if not audiences:
        log.error("oidc[%s]: no configured audience — provider misconfigured", provider)
        raise OAuthProviderUnavailable()

    try:
        header = jwt.get_unverified_header(id_token)
    except jwt.InvalidTokenError as exc:
        log.info("oidc[%s]: malformed header (%s)", provider, type(exc).__name__)
        raise OAuthIdTokenInvalid() from exc
    kid = header.get("kid")
    if not kid:
        log.info("oidc[%s]: missing kid", provider)
        raise OAuthIdTokenInvalid()

    jwks = await _get_jwks(provider, url)
    matching = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)
    if matching is None:
        log.info("oidc[%s]: kid not in JWKS", provider)
        raise OAuthIdTokenInvalid()

    try:
        key = jwt.PyJWK(matching).key
        payload = jwt.decode(
            id_token,
            key,
            algorithms=algorithms,
            audience=audiences,  # never None — empty audiences rejected above
            leeway=300,  # ±5 min skew
        )
    except jwt.InvalidTokenError as exc:
        log.info("oidc[%s]: decode rejected (%s)", provider, type(exc).__name__)
        raise OAuthIdTokenInvalid() from exc

    # Issuer is validated manually so a provider with multiple valid issuers
    # (Google: with/without https) works across PyJWT versions.
    if payload.get("iss") not in issuers:
        log.info("oidc[%s]: issuer mismatch", provider)
        raise OAuthIdTokenInvalid()

    if expected_nonce is not None:
        expected = _hashed_nonce(expected_nonce) if hash_nonce else expected_nonce
        if payload.get("nonce") != expected:
            log.info("oidc[%s]: nonce mismatch", provider)
            raise OAuthIdTokenInvalid()

    return OidcClaims(
        sub=str(payload["sub"]),
        email=payload.get("email"),
        name=payload.get("name"),
        picture=payload.get("picture"),
    )


async def verify_oauth_id_token(
    provider: str, id_token: str, *, expected_nonce: str | None = None
) -> OidcClaims:
    """Verify a provider OIDC id_token → OidcClaims. provider ∈ {kakao, google, apple}.

    Raises OAuthIdTokenInvalid (bad token), OAuthProviderUnavailable (JWKS down),
    or ValidationFailed (unknown provider).
    """
    if provider == "kakao":
        c = await _verify_kakao(id_token, expected_nonce=expected_nonce)
        return OidcClaims(sub=c.sub, email=c.email, name=c.nickname, picture=c.picture)
    if provider == "google":
        return await _verify_generic(
            provider="google",
            url=settings.GOOGLE_JWKS_URL,
            issuers=settings.GOOGLE_OIDC_ISSUERS,
            audiences=settings.GOOGLE_CLIENT_IDS,
            algorithms=["RS256"],
            id_token=id_token,
            expected_nonce=expected_nonce,
            hash_nonce=False,
        )
    if provider == "apple":
        return await _verify_generic(
            provider="apple",
            url=settings.APPLE_JWKS_URL,
            issuers=[settings.APPLE_OIDC_ISSUER],
            audiences=[settings.APPLE_BUNDLE_ID] if settings.APPLE_BUNDLE_ID else [],
            algorithms=["RS256"],  # Apple id_tokens are RS256-signed
            id_token=id_token,
            expected_nonce=expected_nonce,
            hash_nonce=True,
        )
    raise ValidationFailed()
