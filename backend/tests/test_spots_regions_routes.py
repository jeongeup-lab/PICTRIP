"""Integration tests for GET /v1/regions.

The 17 sido are reference data seeded by migration 0003 (`_REGIONS_SEED`), so
these read-only tests need no per-test seeding — they assert the route exposes
that seeded set through the `{ data }` envelope.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.main import app


@pytest_asyncio.fixture(autouse=True)
async def override_db() -> AsyncIterator[None]:
    """Bind get_db to a fresh NullPool engine per test.

    The shared module-level engine is unsafe across pytest-asyncio's
    function-scoped event loops (see tests/conftest.py db_session). The 17 sido
    are committed migration data, so no seeding is needed — a plain session sees
    them.
    """
    from app.core.db import get_db

    eng = create_async_engine(str(settings.sqlalchemy_database_url), poolclass=NullPool)

    async def _override() -> AsyncIterator[AsyncSession]:
        session = AsyncSession(bind=eng, expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()

    app.dependency_overrides[get_db] = _override
    try:
        yield
    finally:
        app.dependency_overrides.clear()
        await eng.dispose()


@pytest.mark.asyncio
async def test_regions_returns_all_17_sido(client: AsyncClient) -> None:
    resp = await client.get("/v1/regions")
    assert resp.status_code == 200
    data = resp.json()["data"]

    # 17 sido, ordered by legal-dong sido code (Seoul 11 → Jeonbuk 52).
    assert len(data) == 17
    codes = [r["code"] for r in data]
    assert codes == sorted(codes)
    assert codes[0] == "11"

    by_code = {r["code"]: r["name"] for r in data}
    assert by_code["11"] == "서울특별시"
    assert by_code["51"] == "강원특별자치도"
    assert by_code["50"] == "제주특별자치도"


@pytest.mark.asyncio
async def test_regions_items_have_code_and_name_only(client: AsyncClient) -> None:
    resp = await client.get("/v1/regions")
    assert resp.status_code == 200
    for region in resp.json()["data"]:
        assert set(region) == {"code", "name"}
        assert region["code"]
        assert region["name"]
