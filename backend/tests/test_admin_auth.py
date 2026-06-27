"""ADM-001 — DB-backed HTTP Basic auth gate on /admin/* (A01 §1.3).

Auth checks the ``admin_users`` table (username + bcrypt hash), not an env var.
Migration 0016 seeds ``admin``/``admin`` into the migrated test DB, so the
authorized path uses that fixed credential. Covers authorized (200 HTML),
wrong-password / wrong-username / missing-credentials (401 + WWW-Authenticate),
and the no-admin-row case (401) by clearing the table in a rolled-back tx.

Every test overrides ``get_db`` with the function-scoped ``db_session`` (a fresh
NullPool engine + per-test transaction) so the verify_admin lookup never touches
the module-level engine across event loops — the same pattern the other admin
tests use.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.main import app

# Seeded by migration 0016.
_USERNAME = "admin"
_PASSWORD = "admin"


@pytest.fixture(autouse=True)
def _use_test_db(db_session: AsyncSession) -> Iterator[None]:
    """Route every /admin auth lookup through the per-test transaction."""
    app.dependency_overrides[get_db] = lambda: db_session
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/admin", "/admin/history", "/admin/health"])
async def test_admin_correct_password_serves_html(client: AsyncClient, path: str) -> None:
    resp = await client.get(path, auth=(_USERNAME, _PASSWORD))
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    assert "<html" in resp.text.lower()
    # security headers present on served admin HTML (no exact CSP assert — brittle)
    assert resp.headers["x-frame-options"] == "DENY"


@pytest.mark.asyncio
async def test_admin_index_trailing_slash_serves_html(client: AsyncClient) -> None:
    """GET /admin/ (trailing slash, common behind proxies) serves the index, not 404."""
    resp = await client.get("/admin/", auth=(_USERNAME, _PASSWORD))
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    assert "<html" in resp.text.lower()


@pytest.mark.asyncio
async def test_admin_wrong_password_returns_401_with_challenge(client: AsyncClient) -> None:
    resp = await client.get("/admin", auth=(_USERNAME, "wrong"))
    assert resp.status_code == 401
    assert resp.headers["www-authenticate"] == "Basic"
    assert resp.json()["error"]["code"] == "ADMIN_UNAUTHORIZED"


@pytest.mark.asyncio
async def test_admin_wrong_username_returns_401(client: AsyncClient) -> None:
    resp = await client.get("/admin", auth=("nobody", _PASSWORD))
    assert resp.status_code == 401
    assert resp.headers["www-authenticate"] == "Basic"
    assert resp.json()["error"]["code"] == "ADMIN_UNAUTHORIZED"


@pytest.mark.asyncio
async def test_admin_missing_credentials_returns_401_with_challenge(client: AsyncClient) -> None:
    resp = await client.get("/admin")
    assert resp.status_code == 401
    assert resp.headers["www-authenticate"] == "Basic"
    assert resp.json()["error"]["code"] == "ADMIN_UNAUTHORIZED"


@pytest.mark.asyncio
async def test_admin_index_trailing_slash_requires_auth(client: AsyncClient) -> None:
    """/admin/ is gated by AdminAuth just like /admin."""
    resp = await client.get("/admin/")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "ADMIN_UNAUTHORIZED"


@pytest.mark.asyncio
async def test_admin_no_admin_row_returns_401(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """With the admin_users table empty, even the seeded creds get 401 (no 503)."""
    await db_session.execute(text("DELETE FROM admin_users"))
    resp = await client.get("/admin", auth=(_USERNAME, _PASSWORD))
    assert resp.status_code == 401
    assert resp.headers["www-authenticate"] == "Basic"
    assert resp.json()["error"]["code"] == "ADMIN_UNAUTHORIZED"
