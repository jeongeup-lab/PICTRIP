"""Provider-agnostic OIDC verification (app.core.oidc).

Reuses the RSA `kakao_signing_key` fixture (conftest) to mint Google id_tokens
signed by a fake JWKS, served via httpx_mock at the Google certs URL.
"""

from __future__ import annotations

import time

import jwt
import pytest
from cryptography.hazmat.primitives import serialization

from app.core.exceptions import OAuthIdTokenInvalid, ValidationFailed
from app.core.oidc import _jwks_caches, verify_oauth_id_token

_GOOGLE_CERTS_URL = "https://www.googleapis.com/oauth2/v3/certs"


@pytest.fixture(autouse=True)
def _clear_oidc_cache():
    # Otherwise a cached fake JWKS is served without a fetch, leaving the
    # httpx_mock response unused (pytest-httpx then errors).
    _jwks_caches.clear()
    yield
    _jwks_caches.clear()


def _mint_google(
    key, *, aud: str, iss: str = "https://accounts.google.com", sub: str = "g-1"
) -> str:
    now = int(time.time())
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return jwt.encode(
        {"iss": iss, "aud": aud, "sub": sub, "iat": now, "exp": now + 600, "name": "G"},
        pem,
        algorithm="RS256",
        headers={"kid": "test-kid-1"},
    )


@pytest.mark.asyncio
async def test_unknown_provider_rejected():
    with pytest.raises(ValidationFailed):
        await verify_oauth_id_token("myspace", "x.y.z", expected_nonce=None)


@pytest.mark.asyncio
async def test_google_bad_audience_rejected(httpx_mock, kakao_signing_key, monkeypatch):
    priv, jwks = kakao_signing_key
    monkeypatch.setattr("app.config.settings.GOOGLE_CLIENT_IDS", ["correct-client"])
    httpx_mock.add_response(url=_GOOGLE_CERTS_URL, json=jwks)
    token = _mint_google(priv, aud="wrong-client")
    with pytest.raises(OAuthIdTokenInvalid):
        await verify_oauth_id_token("google", token, expected_nonce=None)


@pytest.mark.asyncio
async def test_google_wrong_issuer_rejected(httpx_mock, kakao_signing_key, monkeypatch):
    priv, jwks = kakao_signing_key
    monkeypatch.setattr("app.config.settings.GOOGLE_CLIENT_IDS", ["correct-client"])
    httpx_mock.add_response(url=_GOOGLE_CERTS_URL, json=jwks)
    token = _mint_google(priv, aud="correct-client", iss="https://evil.example.com")
    with pytest.raises(OAuthIdTokenInvalid):
        await verify_oauth_id_token("google", token, expected_nonce=None)


@pytest.mark.asyncio
async def test_google_happy_path(httpx_mock, kakao_signing_key, monkeypatch):
    priv, jwks = kakao_signing_key
    monkeypatch.setattr("app.config.settings.GOOGLE_CLIENT_IDS", ["correct-client"])
    httpx_mock.add_response(url=_GOOGLE_CERTS_URL, json=jwks)
    token = _mint_google(priv, aud="correct-client", sub="g-42")
    claims = await verify_oauth_id_token("google", token, expected_nonce=None)
    assert claims.sub == "g-42"
    assert claims.name == "G"
