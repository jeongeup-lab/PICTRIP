from __future__ import annotations

import time

import jwt
import pytest
from cryptography.hazmat.primitives import serialization

from app.modules.users.oidc import _jwks_caches, verify_oauth_id_token
from app.web.errors import (
    OAuthIdTokenInvalid,
    OAuthProviderUnavailable,
    ValidationFailed,
)

_APPLE_KEYS_URL = "https://appleid.apple.com/auth/keys"
_APPLE_ISSUER = "https://appleid.apple.com"


@pytest.fixture(autouse=True)
def _clear_oidc_cache():
    _jwks_caches.clear()
    yield
    _jwks_caches.clear()


def _mint(key, *, aud: str, iss: str = _APPLE_ISSUER, sub: str = "a-1") -> str:
    now = int(time.time())
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return jwt.encode(
        {"iss": iss, "aud": aud, "sub": sub, "iat": now, "exp": now + 600, "name": "A"},
        pem,
        algorithm="RS256",
        headers={"kid": "test-kid-1"},
    )


@pytest.mark.asyncio
async def test_unknown_provider_rejected():
    with pytest.raises(ValidationFailed):
        await verify_oauth_id_token("myspace", "x.y.z", expected_nonce=None)


@pytest.mark.asyncio
async def test_google_is_no_longer_a_supported_provider(kakao_signing_key):
    priv, _ = kakao_signing_key
    token = _mint(priv, aud="any-client", iss="https://accounts.google.com", sub="g-1")
    with pytest.raises(ValidationFailed):
        await verify_oauth_id_token("google", token, expected_nonce=None)


@pytest.mark.asyncio
async def test_apple_bad_audience_rejected(httpx_mock, kakao_signing_key, monkeypatch):
    priv, jwks = kakao_signing_key
    monkeypatch.setattr("app.config.settings.APPLE_BUNDLE_ID", "com.jeongeup.pictrip")
    httpx_mock.add_response(url=_APPLE_KEYS_URL, json=jwks)
    token = _mint(priv, aud="com.someone.else")
    with pytest.raises(OAuthIdTokenInvalid):
        await verify_oauth_id_token("apple", token, expected_nonce=None)


@pytest.mark.asyncio
async def test_apple_wrong_issuer_rejected(httpx_mock, kakao_signing_key, monkeypatch):
    priv, jwks = kakao_signing_key
    monkeypatch.setattr("app.config.settings.APPLE_BUNDLE_ID", "com.jeongeup.pictrip")
    httpx_mock.add_response(url=_APPLE_KEYS_URL, json=jwks)
    token = _mint(priv, aud="com.jeongeup.pictrip", iss="https://evil.example.com")
    with pytest.raises(OAuthIdTokenInvalid):
        await verify_oauth_id_token("apple", token, expected_nonce=None)


@pytest.mark.asyncio
async def test_apple_happy_path(httpx_mock, kakao_signing_key, monkeypatch):
    priv, jwks = kakao_signing_key
    monkeypatch.setattr("app.config.settings.APPLE_BUNDLE_ID", "com.jeongeup.pictrip")
    httpx_mock.add_response(url=_APPLE_KEYS_URL, json=jwks)
    token = _mint(priv, aud="com.jeongeup.pictrip", sub="a-42")
    claims = await verify_oauth_id_token("apple", token, expected_nonce=None)
    assert claims.sub == "a-42"
    assert claims.name == "A"


@pytest.mark.asyncio
async def test_apple_rejected_when_no_bundle_id_configured(kakao_signing_key, monkeypatch):
    priv, _ = kakao_signing_key
    monkeypatch.setattr("app.config.settings.APPLE_BUNDLE_ID", None)
    token = _mint(priv, aud="any.bundle.id", sub="a-1")
    with pytest.raises(OAuthProviderUnavailable):
        await verify_oauth_id_token("apple", token, expected_nonce=None)
