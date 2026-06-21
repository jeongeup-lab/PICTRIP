"""Integration tests for the 전국 집중률 TOP route.

  GET /v1/spots/trending?region=&limit=  — KTO 관광지 집중률 ranking (ADR-0016)

Seeds spots + spot_concentration rows; the source table is name-matched offline by
``scripts/sync_concentration.py``, so here we seed the joined result directly.
Pattern mirrors tests/test_spt_search_routes.py (single-connection rollback).
Region codes ("11" Seoul, "51" Gangwon) are seeded by migration 0003.
"""

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


async def _seed(
    session: AsyncSession,
    *,
    content_id: str,
    title: str,
    rate: float,
    region: str | None = None,
    show_flag: int = 1,
    has_image: bool = True,
    with_concentration: bool = True,
) -> None:
    image = "'http://kto/first.jpg'" if has_image else "NULL"
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, first_image_url, "
            "addr1, ldong_regn_cd, mapx, mapy, show_flag) "
            f"VALUES (:cid, 12, :t, {image}, '주소', :r, 127.0, 37.5, :sf) "
            "ON CONFLICT (content_id) DO NOTHING"
        ),
        {"cid": content_id, "t": title, "r": region, "sf": show_flag},
    )
    if with_concentration:
        await session.execute(
            text(
                "INSERT INTO spot_concentration "
                "(content_id, concentration_rate, base_ymd, raw_name, signgu_cd) "
                "VALUES (:cid, :rate, '2026-06-06', :t, NULL) "
                "ON CONFLICT (content_id) DO NOTHING"
            ),
            {"cid": content_id, "rate": rate, "t": title},
        )
    await session.commit()


@pytest.mark.asyncio
async def test_trending_orders_by_rate_desc_with_rank(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    await _seed(override_db_and_seed, content_id="TR-LOW", title="낮은 곳", rate=40.0)
    await _seed(override_db_and_seed, content_id="TR-HIGH", title="붐비는 곳", rate=98.5)
    await _seed(override_db_and_seed, content_id="TR-MID", title="중간 곳", rate=70.0)

    resp = await client.get("/v1/spots/trending")

    assert resp.status_code == 200
    body = resp.json()
    assert body["error"] is None
    data = body["data"]
    assert [c["contentId"] for c in data] == ["TR-HIGH", "TR-MID", "TR-LOW"]
    assert [c["rank"] for c in data] == [1, 2, 3]
    assert data[0]["concentrationRate"] == 98.5


@pytest.mark.asyncio
async def test_trending_region_filter(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    await _seed(
        override_db_and_seed, content_id="TR-SEOUL", title="서울 곳", rate=90.0, region="11"
    )
    await _seed(override_db_and_seed, content_id="TR-GW", title="강원 곳", rate=95.0, region="51")

    resp = await client.get("/v1/spots/trending", params={"region": "51"})

    ids = [c["contentId"] for c in resp.json()["data"]]
    assert ids == ["TR-GW"]


@pytest.mark.asyncio
async def test_trending_excludes_hidden_and_imageless(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    await _seed(override_db_and_seed, content_id="TR-HIDDEN", title="숨김", rate=99.0, show_flag=0)
    await _seed(
        override_db_and_seed, content_id="TR-NOIMG", title="이미지없음", rate=99.0, has_image=False
    )
    await _seed(override_db_and_seed, content_id="TR-OK", title="정상", rate=10.0)

    resp = await client.get("/v1/spots/trending")

    ids = [c["contentId"] for c in resp.json()["data"]]
    assert ids == ["TR-OK"]


@pytest.mark.asyncio
async def test_trending_excludes_spots_without_concentration(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    await _seed(
        override_db_and_seed,
        content_id="TR-NOCONC",
        title="집중률없음",
        rate=0.0,
        with_concentration=False,
    )
    await _seed(override_db_and_seed, content_id="TR-HAS", title="집중률있음", rate=50.0)

    resp = await client.get("/v1/spots/trending")

    ids = [c["contentId"] for c in resp.json()["data"]]
    assert ids == ["TR-HAS"]


@pytest.mark.asyncio
async def test_trending_respects_limit(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    for i in range(5):
        await _seed(override_db_and_seed, content_id=f"TR-{i}", title=f"곳{i}", rate=float(i))

    resp = await client.get("/v1/spots/trending", params={"limit": 2})

    assert len(resp.json()["data"]) == 2


@pytest.mark.asyncio
async def test_trending_unknown_region_is_422(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    resp = await client.get("/v1/spots/trending", params={"region": "99"})

    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_FAILED"
