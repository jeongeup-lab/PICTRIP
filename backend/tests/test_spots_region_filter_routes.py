"""Integration tests for the region filter on GET /v1/moods/{code}/spots."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
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
                bind=conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
            )

            async def _override() -> AsyncIterator[AsyncSession]:
                session = AsyncSession(
                    bind=conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
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


async def _seed_spot_in_region(
    session: AsyncSession, content_id: str, mood_code: str, region_cd: str
) -> None:
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, first_image_url, "
            "show_flag, ldong_regn_cd) "
            "VALUES (:cid, 12, :t, 'http://kto/i.jpg', 1, :rc) "
            "ON CONFLICT (content_id) DO NOTHING"
        ),
        {"cid": content_id, "t": f"title-{content_id}", "rc": region_cd},
    )
    await session.execute(
        text(
            "INSERT INTO spot_moods (content_id, mood_id, confidence, source) "
            "SELECT :cid, id, 1.0, 'manual' FROM moods WHERE code = :code "
            "ON CONFLICT DO NOTHING"
        ),
        {"cid": content_id, "code": mood_code},
    )
    await session.commit()


@pytest.mark.asyncio
async def test_region_param_filters(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    await _seed_spot_in_region(override_db_and_seed, "rfr_gangwon", "sea", "51")
    await _seed_spot_in_region(override_db_and_seed, "rfr_jeju", "sea", "50")

    resp = await client.get("/v1/moods/sea/spots?limit=10000&region=51")

    assert resp.status_code == 200
    cids = {item["contentId"] for item in resp.json()["data"]}
    assert "rfr_gangwon" in cids
    assert "rfr_jeju" not in cids


@pytest.mark.asyncio
async def test_no_region_param_unchanged(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    await _seed_spot_in_region(override_db_and_seed, "rfr_g2", "sea", "51")
    await _seed_spot_in_region(override_db_and_seed, "rfr_j2", "sea", "50")

    resp = await client.get("/v1/moods/sea/spots?limit=10000")

    assert resp.status_code == 200
    cids = {item["contentId"] for item in resp.json()["data"]}
    assert {"rfr_g2", "rfr_j2"}.issubset(cids)


@pytest.mark.asyncio
async def test_unknown_region_returns_422(client: AsyncClient) -> None:
    resp = await client.get("/v1/moods/sea/spots?region=99")
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_FAILED"
