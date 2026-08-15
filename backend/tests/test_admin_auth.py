from __future__ import annotations

from collections.abc import Iterator

import pytest
from fakeredis.aioredis import FakeRedis
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.redis import get_redis
from app.main import app

_USERNAME = "admin"
_PASSWORD = "admin"


@pytest.fixture(autouse=True)
def _use_test_db(db_session: AsyncSession) -> Iterator[None]:
    fake = FakeRedis(decode_responses=True)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_redis] = lambda: fake
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
@pytest.mark.parametrize("path", ["/admin", "/admin/", "/admin/history", "/admin/overseas"])
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

    page = await client.get("/admin")
    assert page.status_code == 200
    assert page.headers["content-type"].startswith("text/html")
    assert page.headers["x-frame-options"] == "DENY"


@pytest.mark.asyncio
@pytest.mark.parametrize("user,pw", [(_USERNAME, "wrong"), ("nobody", _PASSWORD)])
async def test_login_bad_credentials_bounce_back(client: AsyncClient, user: str, pw: str) -> None:
    resp = await _login(client, user, pw)
    assert resp.status_code == 303
    assert resp.headers["location"].endswith("/admin/login?error=1")
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


@pytest.mark.asyncio
async def test_login_rate_limited_after_threshold(client: AsyncClient) -> None:
    statuses = [(await _login(client, _USERNAME, "wrong")).status_code for _ in range(6)]
    assert statuses[:5] == [303] * 5
    assert statuses[5] == 429
    over = await _login(client, _USERNAME, "wrong")
    assert over.status_code == 429
    assert over.json()["error"]["code"] == "RATE_LIMITED"


@pytest.mark.asyncio
async def test_admin_assets_are_not_cached(client: AsyncClient) -> None:
    resp = await client.get("/admin/assets/admin.css")
    assert resp.status_code == 200
    assert resp.headers["cache-control"] == "no-store"
