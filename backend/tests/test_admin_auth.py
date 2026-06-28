"""ADM-001 — login page + signed-cookie session gate on /admin/* (A01 §1.3).

Credentials are checked against the ``admin_users`` table (username + bcrypt
hash); migration 0016 seeds ``admin``/``admin`` into the migrated test DB. The
console no longer uses HTTP Basic: HTML pages redirect to /admin/login when
logged out, /admin/api/* returns 401 (no WWW-Authenticate), and a successful
POST /admin/login sets a session cookie that authorizes later requests.

Every test routes the auth lookup through the function-scoped ``db_session`` via
the ``get_db`` override so it never touches the module-level engine across loops.
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


async def _login(client: AsyncClient, username: str = _USERNAME, password: str = _PASSWORD):
    return await client.post("/admin/login", data={"username": username, "password": password})


@pytest.mark.asyncio
async def test_login_page_is_public(client: AsyncClient) -> None:
    resp = await client.get("/admin/login")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    assert "관리자 로그인" in resp.text


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/admin", "/admin/", "/admin/history", "/admin/curation"])
async def test_protected_page_redirects_to_login_when_logged_out(
    client: AsyncClient, path: str
) -> None:
    resp = await client.get(path)
    assert resp.status_code == 303
    assert resp.headers["location"].endswith("/admin/login")


@pytest.mark.asyncio
async def test_api_returns_401_without_basic_challenge(client: AsyncClient) -> None:
    resp = await client.get("/admin/api/collection")
    assert resp.status_code == 401
    assert "www-authenticate" not in {k.lower() for k in resp.headers}
    assert resp.json()["error"]["code"] == "ADMIN_UNAUTHORIZED"


@pytest.mark.asyncio
async def test_login_success_then_page_served(client: AsyncClient) -> None:
    login = await _login(client)
    assert login.status_code == 303
    assert login.headers["location"].endswith("/admin")

    page = await client.get("/admin")  # cookie carried by the client
    assert page.status_code == 200
    assert page.headers["content-type"].startswith("text/html")
    assert page.headers["x-frame-options"] == "DENY"


@pytest.mark.asyncio
@pytest.mark.parametrize("user,pw", [(_USERNAME, "wrong"), ("nobody", _PASSWORD)])
async def test_login_bad_credentials_bounce_back(client: AsyncClient, user: str, pw: str) -> None:
    resp = await _login(client, user, pw)
    assert resp.status_code == 303
    assert resp.headers["location"].endswith("/admin/login?error=1")
    # still logged out
    page = await client.get("/admin")
    assert page.status_code == 303
    assert page.headers["location"].endswith("/admin/login")


@pytest.mark.asyncio
async def test_logout_clears_session(client: AsyncClient) -> None:
    await _login(client)
    assert (await client.get("/admin")).status_code == 200

    out = await client.post("/admin/logout")
    assert out.status_code == 303
    assert out.headers["location"].endswith("/admin/login")

    page = await client.get("/admin")
    assert page.status_code == 303
    assert page.headers["location"].endswith("/admin/login")


@pytest.mark.asyncio
async def test_no_admin_row_rejects_login(client: AsyncClient, db_session: AsyncSession) -> None:
    await db_session.execute(text("DELETE FROM admin_users"))
    resp = await _login(client)
    assert resp.status_code == 303
    assert resp.headers["location"].endswith("/admin/login?error=1")
