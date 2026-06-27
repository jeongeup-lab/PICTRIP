"""ADM-001 — HTTP Basic auth gate on /admin/* (A01 §1.3).

Covers the locked (503), wrong-credentials (401 + WWW-Authenticate), and
authorized (200 HTML) paths. The JSON API (/admin/api/*) is a later slice and is
not exercised here.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.config import settings

_PASSWORD = "s3cret-admin-pw"


@pytest.fixture
def admin_password(monkeypatch: pytest.MonkeyPatch) -> str:
    """Configure ADMIN_PASSWORD on the live settings singleton for one test."""
    monkeypatch.setattr(settings, "ADMIN_PASSWORD", _PASSWORD)
    return _PASSWORD


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/admin", "/admin/history", "/admin/health"])
async def test_admin_locked_when_password_unset(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    monkeypatch.setattr(settings, "ADMIN_PASSWORD", None)
    resp = await client.get(path, auth=("admin", "anything"))
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "ADMIN_LOCKED"


@pytest.mark.asyncio
async def test_admin_wrong_password_returns_401_with_challenge(
    client: AsyncClient, admin_password: str
) -> None:
    resp = await client.get("/admin", auth=("admin", "wrong"))
    assert resp.status_code == 401
    assert resp.headers["www-authenticate"] == "Basic"
    assert resp.json()["error"]["code"] == "ADMIN_UNAUTHORIZED"


@pytest.mark.asyncio
async def test_admin_wrong_username_returns_401(client: AsyncClient, admin_password: str) -> None:
    resp = await client.get("/admin", auth=("root", admin_password))
    assert resp.status_code == 401
    assert resp.headers["www-authenticate"] == "Basic"
    assert resp.json()["error"]["code"] == "ADMIN_UNAUTHORIZED"


@pytest.mark.asyncio
async def test_admin_missing_credentials_returns_401_with_challenge(
    client: AsyncClient, admin_password: str
) -> None:
    resp = await client.get("/admin")
    assert resp.status_code == 401
    assert resp.headers["www-authenticate"] == "Basic"
    assert resp.json()["error"]["code"] == "ADMIN_UNAUTHORIZED"


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/admin", "/admin/history", "/admin/health"])
async def test_admin_correct_password_serves_html(
    client: AsyncClient, admin_password: str, path: str
) -> None:
    resp = await client.get(path, auth=("admin", admin_password))
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    assert "<html" in resp.text.lower()
    # security headers present on served admin HTML (no exact CSP assert — brittle)
    assert resp.headers["x-frame-options"] == "DENY"


@pytest.mark.asyncio
async def test_admin_index_trailing_slash_serves_html(
    client: AsyncClient, admin_password: str
) -> None:
    """GET /admin/ (trailing slash, common behind proxies) serves the index, not 404."""
    resp = await client.get("/admin/", auth=("admin", admin_password))
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    assert "<html" in resp.text.lower()


@pytest.mark.asyncio
async def test_admin_index_trailing_slash_requires_auth(
    client: AsyncClient, admin_password: str
) -> None:
    """/admin/ is gated by AdminAuth just like /admin."""
    resp = await client.get("/admin/")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "ADMIN_UNAUTHORIZED"
