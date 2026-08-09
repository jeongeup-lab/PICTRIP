from __future__ import annotations

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from app.modules.users import apple_tokens

_TOKEN_URL = "https://appleid.apple.com/auth/token"
_REVOKE_URL = "https://appleid.apple.com/auth/revoke"


@pytest.fixture
def apple_key(monkeypatch):
    key = ec.generate_private_key(ec.SECP256R1())
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    monkeypatch.setattr("app.config.settings.APPLE_TEAM_ID", "TEAM123456")
    monkeypatch.setattr("app.config.settings.APPLE_KEY_ID", "KEY1234567")
    monkeypatch.setattr("app.config.settings.APPLE_PRIVATE_KEY", pem.replace("\n", "\\n"))
    monkeypatch.setattr("app.config.settings.APPLE_BUNDLE_ID", "com.jeongeup.pictrip")
    return key


def test_is_configured_false_without_key(monkeypatch):
    monkeypatch.setattr("app.config.settings.APPLE_PRIVATE_KEY", "")
    assert apple_tokens.is_configured() is False


def test_build_client_secret_is_es256_signed_with_key_id(apple_key):
    token = apple_tokens.build_client_secret()

    assert jwt.get_unverified_header(token)["kid"] == "KEY1234567"
    payload = jwt.decode(
        token,
        apple_key.public_key(),
        algorithms=["ES256"],
        audience="https://appleid.apple.com",
    )
    assert payload["iss"] == "TEAM123456"
    assert payload["sub"] == "com.jeongeup.pictrip"
    assert payload["exp"] > payload["iat"]


@pytest.mark.asyncio
async def test_exchange_returns_refresh_token(httpx_mock, apple_key):
    httpx_mock.add_response(url=_TOKEN_URL, json={"refresh_token": "r-apple-1"})
    assert await apple_tokens.exchange_authorization_code("code-1") == "r-apple-1"


@pytest.mark.asyncio
async def test_exchange_returns_none_on_rejection(httpx_mock, apple_key):
    httpx_mock.add_response(url=_TOKEN_URL, status_code=400, json={"error": "invalid_grant"})
    assert await apple_tokens.exchange_authorization_code("code-1") is None


@pytest.mark.asyncio
async def test_exchange_skipped_when_key_missing(monkeypatch):
    monkeypatch.setattr("app.config.settings.APPLE_PRIVATE_KEY", "")
    assert await apple_tokens.exchange_authorization_code("code-1") is None


@pytest.mark.asyncio
async def test_revoke_reports_success(httpx_mock, apple_key):
    httpx_mock.add_response(url=_REVOKE_URL, status_code=200, text="")
    assert await apple_tokens.revoke_refresh_token("r-apple-1") is True


@pytest.mark.asyncio
async def test_revoke_reports_failure_without_raising(httpx_mock, apple_key):
    httpx_mock.add_response(url=_REVOKE_URL, status_code=400, json={"error": "invalid_request"})
    assert await apple_tokens.revoke_refresh_token("r-apple-1") is False
