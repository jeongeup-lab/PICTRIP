"""Integration tests for GET /v1/spots/by-region.

Region-code union (signgu and/or regn), image-only, 집중률-desc order.
DB fixture mirrors tests/test_spots_search_routes.py (outer-tx rollback).
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


async def _ensure_region_refs(
    session: AsyncSession, *, signgu: str | None, regn: str | None
) -> None:
    """Satisfy the spots FK chain regions <- sigungus <- spots.

    `spots.ldong_signgu_cd` FKs `sigungus`, which itself FKs `regions`; a signgu
    code's parent 시도 is its first two digits. The test DB ships the 17 regions
    but no sigungus, so seed any parent rows the spot needs (idempotent).
    """
    regn_codes = {c for c in (regn, signgu[:2] if signgu else None) if c}
    for code in regn_codes:
        await session.execute(
            text(
                "INSERT INTO regions (ldong_regn_cd, ldong_regn_nm) "
                "VALUES (:c, :c) ON CONFLICT (ldong_regn_cd) DO NOTHING"
            ),
            {"c": code},
        )
    if signgu:
        await session.execute(
            text(
                "INSERT INTO sigungus (ldong_signgu_cd, ldong_regn_cd, ldong_signgu_nm) "
                "VALUES (:s, :r, :s) ON CONFLICT (ldong_signgu_cd) DO NOTHING"
            ),
            {"s": signgu, "r": signgu[:2]},
        )


async def _seed_spot(
    session: AsyncSession,
    *,
    content_id: str,
    title: str,
    signgu: str | None = None,
    regn: str | None = None,
    image: str = "http://kto/first.jpg",
    show_flag: int = 1,
) -> None:
    await _ensure_region_refs(session, signgu=signgu, regn=regn)
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, first_image_url, "
            "addr1, ldong_regn_cd, ldong_signgu_cd, mapx, mapy, show_flag) "
            "VALUES (:cid, 12, :t, :img, '주소', :r, :s, 127.0, 37.5, :sf) "
            "ON CONFLICT (content_id) DO NOTHING"
        ),
        {"cid": content_id, "t": title, "img": image, "r": regn, "s": signgu, "sf": show_flag},
    )
    await session.commit()


async def _seed_concentration(session: AsyncSession, *, content_id: str, rate: float) -> None:
    await session.execute(
        text(
            "INSERT INTO spot_concentration (content_id, concentration_rate, base_ymd, raw_name) "
            "VALUES (:cid, :rate, '2026-01-01', :cid) "
            "ON CONFLICT (content_id) DO UPDATE SET concentration_rate = :rate"
        ),
        {"cid": content_id, "rate": rate},
    )
    await session.commit()


@pytest.mark.asyncio
async def test_by_region_signgu_filter_and_concentration_order(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    s = override_db_and_seed
    await _seed_spot(s, content_id="BR-1", title="가나", signgu="51150")
    await _seed_spot(s, content_id="BR-2", title="다라", signgu="51150")
    await _seed_spot(s, content_id="BR-OTHER", title="타지역", signgu="11110")
    await _seed_concentration(s, content_id="BR-2", rate=9.0)  # higher rate first
    await _seed_concentration(s, content_id="BR-1", rate=1.0)

    r = await client.get("/v1/spots/by-region", params={"signgu": "51150"})
    assert r.status_code == 200
    ids = [c["contentId"] for c in r.json()["data"]]
    assert ids == ["BR-2", "BR-1"]  # rate desc; BR-OTHER excluded


@pytest.mark.asyncio
async def test_by_region_regn_and_signgu_union(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    s = override_db_and_seed
    await _seed_spot(s, content_id="U-SIGNGU", title="A", signgu="52111")
    await _seed_spot(s, content_id="U-REGN", title="B", regn="26")
    r = await client.get("/v1/spots/by-region", params={"signgu": "52111", "regn": "26"})
    assert r.status_code == 200
    ids = {c["contentId"] for c in r.json()["data"]}
    assert ids == {"U-SIGNGU", "U-REGN"}


@pytest.mark.asyncio
async def test_by_region_excludes_imageless_and_hidden(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    s = override_db_and_seed
    await _seed_spot(s, content_id="OK", title="A", signgu="47130")
    await _seed_spot(s, content_id="NOIMG", title="B", signgu="47130", image="")
    await _seed_spot(s, content_id="HIDDEN", title="C", signgu="47130", show_flag=0)
    r = await client.get("/v1/spots/by-region", params={"signgu": "47130"})
    ids = {c["contentId"] for c in r.json()["data"]}
    assert ids == {"OK"}


@pytest.mark.asyncio
async def test_by_region_requires_a_code(client: AsyncClient) -> None:
    r = await client.get("/v1/spots/by-region")
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_FAILED"


@pytest.mark.asyncio
async def test_by_region_limit_clamped(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    r = await client.get("/v1/spots/by-region", params={"signgu": "51150", "limit": 999})
    assert r.status_code == 422  # le=60 → 999 rejected by Query validation
