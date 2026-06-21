"""Integration tests for GET /v1/recommendations/today-inspo."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from fakeredis.aioredis import FakeRedis
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.main import app


@pytest_asyncio.fixture(autouse=True)
async def override_db_and_seed() -> AsyncIterator[AsyncSession]:
    from app.core.db import get_db

    eng = create_async_engine(str(settings.sqlalchemy_database_url), poolclass=NullPool)
    async with eng.connect() as conn:
        tx = await conn.begin()
        try:
            seed = AsyncSession(
                bind=conn,
                expire_on_commit=False,
                join_transaction_mode="create_savepoint",
            )

            async def _override() -> AsyncIterator[AsyncSession]:
                session = AsyncSession(
                    bind=conn,
                    expire_on_commit=False,
                    join_transaction_mode="create_savepoint",
                )
                try:
                    yield session
                finally:
                    await session.close()

            app.dependency_overrides[get_db] = _override
            try:
                yield seed
            finally:
                await seed.close()
                app.dependency_overrides.pop(get_db, None)
        finally:
            if tx.is_active:
                await tx.rollback()
    await eng.dispose()


@pytest.fixture(autouse=True)
def isolate_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.modules.recommendations import services as recommendations_services

    monkeypatch.setattr(recommendations_services, "redis_cache", FakeRedis(decode_responses=False))


async def _insert_spot(session: AsyncSession, content_id: str) -> None:
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, first_image_url, show_flag) "
            "VALUES (:cid, 12, :t, 'http://kto.example/i.jpg', 1) "
            "ON CONFLICT (content_id) DO NOTHING"
        ),
        {"cid": content_id, "t": f"title-{content_id}"},
    )
    await session.commit()


async def _drain_pool(session: AsyncSession) -> None:
    """Empty the eligible pool (seeded DB has ~43k eligible spots)."""
    await session.execute(
        text(
            "UPDATE spots SET show_flag = 0 "
            "WHERE show_flag = 1 AND first_image_url IS NOT NULL AND first_image_url <> ''"
        )
    )
    await session.commit()


@pytest.mark.asyncio
async def test_today_inspo_returns_spotcard_envelope(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    # Drain first so the single inserted spot is the only eligible pick.
    await _drain_pool(override_db_and_seed)
    await _insert_spot(override_db_and_seed, "rti_route_a")

    resp = await client.get("/v1/recommendations/today-inspo")

    assert resp.status_code == 200
    body = resp.json()
    assert body["error"] is None
    data = body["data"]
    assert set(data) >= {"contentId", "title", "firstImageUrl", "addr1", "mapx", "mapy"}
    assert data["contentId"] == "rti_route_a"


@pytest.mark.asyncio
async def test_today_inspo_is_stable_across_requests(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    for cid in ("rti_s1", "rti_s2", "rti_s3"):
        await _insert_spot(override_db_and_seed, cid)

    first = (await client.get("/v1/recommendations/today-inspo")).json()
    second = (await client.get("/v1/recommendations/today-inspo")).json()
    assert first["data"]["contentId"] == second["data"]["contentId"]


@pytest.mark.asyncio
async def test_today_inspo_404_on_empty_pool(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    await _drain_pool(override_db_and_seed)
    resp = await client.get("/v1/recommendations/today-inspo")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
