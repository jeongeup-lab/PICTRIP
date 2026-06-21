"""Integration tests for region-scoped GET /v1/spots/{id}/similar (ADR-0014).

Asserts (1) the `region` query param restricts neighbors to the sido, (2) an
unknown region is a 422, and (3) the `query` object now carries addr1/mapx/mapy
so the map can center on the picked spot. Fixture mirrors
tests/test_spt_discover_routes.py (savepoint-isolated get_db override + a seed
session on the same connection).
"""

from __future__ import annotations

import math
import random
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


def _vec(seed: int, dim: int = 512) -> str:
    rng = random.Random(seed)
    raw = [rng.gauss(0, 1) for _ in range(dim)]
    norm = math.sqrt(sum(x * x for x in raw))
    return "[" + ",".join(f"{x / norm:.6f}" for x in raw) + "]"


async def _seed_spot(
    session: AsyncSession,
    content_id: str,
    region_cd: str,
    *,
    with_coords: bool = False,
) -> None:
    addr1 = "강원 어딘가" if with_coords else None
    mapx = 128.5 if with_coords else None
    mapy = 37.8 if with_coords else None
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, first_image_url, "
            "show_flag, ldong_regn_cd, addr1, mapx, mapy) "
            "VALUES (:cid, 12, :t, 'http://kto.example/i.jpg', 1, :rc, :a, :x, :y) "
            "ON CONFLICT (content_id) DO NOTHING"
        ),
        {
            "cid": content_id,
            "t": f"title-{content_id}",
            "rc": region_cd,
            "a": addr1,
            "x": mapx,
            "y": mapy,
        },
    )
    await session.execute(
        text(
            "INSERT INTO spot_embeddings (content_id, embedding) "
            "VALUES (:cid, (:emb)::halfvec(512)) ON CONFLICT (content_id) DO NOTHING"
        ),
        {"cid": content_id, "emb": _vec(1)},
    )
    await session.commit()


@pytest.mark.asyncio
async def test_region_filters_neighbors_and_query_has_coords(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    seed = override_db_and_seed
    await _seed_spot(seed, "srr_q", "51", with_coords=True)
    await _seed_spot(seed, "srr_gangwon", "51")
    await _seed_spot(seed, "srr_jeju", "50")

    resp = await client.get("/v1/spots/srr_q/similar?region=51&limit=30")
    assert resp.status_code == 200
    body = resp.json()
    assert body["error"] is None

    query = body["data"]["query"]
    assert query["mapx"] == 128.5
    assert query["mapy"] == 37.8
    assert query["addr1"] == "강원 어딘가"

    cids = {n["contentId"] for n in body["data"]["neighbors"]}
    assert "srr_gangwon" in cids
    assert "srr_jeju" not in cids


@pytest.mark.asyncio
async def test_unknown_region_returns_422(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    seed = override_db_and_seed
    await _seed_spot(seed, "srr_u", "51", with_coords=True)

    resp = await client.get("/v1/spots/srr_u/similar?region=99")
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_FAILED"
