"""Integration tests for GET /v1/spots/batch.

content_id CSV → cards, INPUT ORDER PRESERVED; unknown/hidden ids dropped.
DB fixture mirrors tests/test_spots_by_region_routes.py (outer-tx rollback).
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


@pytest.mark.asyncio
async def test_batch_preserves_input_order(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    s = override_db_and_seed
    await _seed_spot(s, content_id="B-1", title="A", signgu="11110")
    await _seed_spot(s, content_id="B-2", title="B", signgu="11110")
    await _seed_spot(s, content_id="B-3", title="C", signgu="11110")
    r = await client.get("/v1/spots/batch", params={"ids": "B-3,B-1,B-2"})
    assert r.status_code == 200
    assert [c["contentId"] for c in r.json()["data"]] == ["B-3", "B-1", "B-2"]


@pytest.mark.asyncio
async def test_batch_drops_unknown_and_hidden(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    s = override_db_and_seed
    await _seed_spot(s, content_id="B-OK", title="A", signgu="11110")
    await _seed_spot(s, content_id="B-HID", title="B", signgu="11110", show_flag=0)
    r = await client.get("/v1/spots/batch", params={"ids": "B-OK,B-HID,B-NOPE"})
    assert [c["contentId"] for c in r.json()["data"]] == ["B-OK"]


@pytest.mark.asyncio
async def test_batch_requires_ids(client: AsyncClient) -> None:
    r = await client.get("/v1/spots/batch")
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_batch_rejects_too_many(client: AsyncClient) -> None:
    ids = ",".join(f"X{i}" for i in range(31))
    r = await client.get("/v1/spots/batch", params={"ids": ids})
    assert r.status_code == 422
