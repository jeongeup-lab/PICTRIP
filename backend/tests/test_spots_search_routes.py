"""Integration tests for the spot text-search route.

  GET /v1/spots/search?q=&region=&limit=  — place-name/location ILIKE on title/addr1

Pattern mirrors tests/test_usr_saved_spots_routes.py: a per-test override binds
both the FastAPI ``get_db`` dependency and the seed session to a single
connection wrapped in an outer transaction rolled back on teardown. The route is
public (no auth). Region codes ("11" Seoul, "51" Gangwon) are seeded by migration 0003.
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


async def _seed_spot(
    session: AsyncSession,
    *,
    content_id: str,
    title: str,
    addr1: str = "주소",
    region: str | None = None,
    show_flag: int = 1,
) -> None:
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, first_image_url, "
            "addr1, ldong_regn_cd, mapx, mapy, show_flag) "
            "VALUES (:cid, 12, :t, 'http://kto/first.jpg', :a, :r, 127.0, 37.5, :sf) "
            "ON CONFLICT (content_id) DO NOTHING"
        ),
        {"cid": content_id, "t": title, "a": addr1, "r": region, "sf": show_flag},
    )
    await session.commit()


@pytest.mark.asyncio
async def test_search_matches_title_substring(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    await _seed_spot(override_db_and_seed, content_id="SR-1", title="제주 바다 산책")
    await _seed_spot(override_db_and_seed, content_id="SR-2", title="서울숲 거리")

    resp = await client.get("/v1/spots/search", params={"q": "바다"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["error"] is None
    ids = [c["contentId"] for c in body["data"]]
    assert ids == ["SR-1"]


@pytest.mark.asyncio
async def test_search_is_case_insensitive_and_matches_addr1(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    await _seed_spot(override_db_and_seed, content_id="SR-3", title="A Cafe", addr1="강원도 속초시")

    by_title = await client.get("/v1/spots/search", params={"q": "cafe"})
    by_addr = await client.get("/v1/spots/search", params={"q": "속초"})

    assert [c["contentId"] for c in by_title.json()["data"]] == ["SR-3"]
    assert [c["contentId"] for c in by_addr.json()["data"]] == ["SR-3"]


@pytest.mark.asyncio
async def test_search_prefix_match_ranks_first(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    # Both contain "한옥"; only SR-PRE starts with it → must come first.
    await _seed_spot(override_db_and_seed, content_id="SR-MID", title="고즈넉한 한옥 골목")
    await _seed_spot(override_db_and_seed, content_id="SR-PRE", title="한옥 마을 전경")

    resp = await client.get("/v1/spots/search", params={"q": "한옥"})

    ids = [c["contentId"] for c in resp.json()["data"]]
    assert ids[0] == "SR-PRE"
    assert set(ids) == {"SR-PRE", "SR-MID"}


@pytest.mark.asyncio
async def test_search_region_filter(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    await _seed_spot(override_db_and_seed, content_id="SR-SEOUL", title="공원 산책", region="11")
    await _seed_spot(override_db_and_seed, content_id="SR-GW", title="공원 호수", region="51")

    resp = await client.get("/v1/spots/search", params={"q": "공원", "region": "51"})

    ids = [c["contentId"] for c in resp.json()["data"]]
    assert ids == ["SR-GW"]


@pytest.mark.asyncio
async def test_search_excludes_hidden_spots(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    await _seed_spot(override_db_and_seed, content_id="SR-HIDDEN", title="숨은 폭포", show_flag=0)

    resp = await client.get("/v1/spots/search", params={"q": "폭포"})

    assert resp.json()["data"] == []


@pytest.mark.asyncio
async def test_search_unknown_region_is_422(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    resp = await client.get("/v1/spots/search", params={"q": "바다", "region": "99"})

    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_FAILED"


@pytest.mark.asyncio
async def test_search_blank_query_returns_empty(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    await _seed_spot(override_db_and_seed, content_id="SR-X", title="아무 곳")

    # A single space passes the min_length=1 query guard but is blank after strip.
    resp = await client.get("/v1/spots/search", params={"q": " "})

    assert resp.status_code == 200
    assert resp.json()["data"] == []


@pytest.mark.asyncio
async def test_search_missing_query_is_422(client: AsyncClient) -> None:
    resp = await client.get("/v1/spots/search")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_search_wildcard_is_literal(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    # A literal '%' must not act as a wildcard matching everything.
    await _seed_spot(override_db_and_seed, content_id="SR-PCT", title="50% 할인 카페")
    await _seed_spot(override_db_and_seed, content_id="SR-OTHER", title="조용한 바다")

    resp = await client.get("/v1/spots/search", params={"q": "%"})

    ids = [c["contentId"] for c in resp.json()["data"]]
    assert ids == ["SR-PCT"]
