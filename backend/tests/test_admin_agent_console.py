from __future__ import annotations

from collections.abc import Iterator

import pytest
from fakeredis.aioredis import FakeRedis
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.redis import get_redis
from app.main import app
from app.security.jwt import decode_token

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _use_test_db(db_session: AsyncSession) -> Iterator[None]:
    fake = FakeRedis(decode_responses=True)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_redis] = lambda: fake
    yield
    app.dependency_overrides.clear()


async def _login(client: AsyncClient) -> None:
    await client.post("/admin/login", data={"username": "admin", "password": "admin"})


async def test_console_is_behind_the_admin_session(client: AsyncClient) -> None:
    """콘솔은 토큰을 발급하므로 로그인 밖에 두면 누구나 남의 계정이 된다."""
    resp = await client.get("/admin/agent")

    assert resp.status_code == 303
    assert resp.headers["location"] == "/admin/login"


async def test_console_page_loads_after_login(client: AsyncClient) -> None:
    await _login(client)

    resp = await client.get("/admin/agent")

    assert resp.status_code == 200
    assert "에이전트 콘솔" in resp.text


async def test_console_reports_the_router_in_use(client: AsyncClient) -> None:
    """구 라우터로 재고 있는 줄 모르면 측정이 통째로 어긋난다."""
    await _login(client)

    resp = await client.get("/admin/api/agent/router")

    assert resp.status_code == 200
    assert resp.json()["data"]["router"] in ("branches", "tools")


async def test_console_mints_a_token_for_the_asked_user(client: AsyncClient) -> None:
    """저장 기준 추천은 로그인한 사용자로만 볼 수 있다."""
    await _login(client)

    resp = await client.get("/admin/api/agent/token", params={"user_id": 7})

    assert resp.status_code == 200
    assert decode_token(resp.json()["data"]["token"])["sub"] == "7"


async def test_token_endpoint_needs_the_admin_session(client: AsyncClient) -> None:
    resp = await client.get("/admin/api/agent/token", params={"user_id": 7})

    assert resp.status_code in (401, 303)
