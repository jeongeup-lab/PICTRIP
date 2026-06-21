"""Integration tests for the discover routes.

Routes under test:
  GET /v1/moods/{moodCode}/spots
  GET /v1/spots/{contentId}/similar

Pattern mirrors tests/test_usr_auth_routes.py: a per-test override binds
both the FastAPI ``get_db`` dependency and the seed session to a single
connection wrapped in an outer transaction that is rolled back on teardown.
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
    """Override get_db with a savepoint-isolated session, and yield a seed
    session bound to the same connection so tests can pre-populate rows
    that the route handler will then see.
    """
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


async def _insert_spot_with_mood(session: AsyncSession, content_id: str, mood_code: str) -> None:
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, first_image_url, show_flag) "
            "VALUES (:cid, 12, :t, 'http://kto.example/i.jpg', 1) "
            "ON CONFLICT (content_id) DO NOTHING"
        ),
        {"cid": content_id, "t": f"title-{content_id}"},
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


async def _insert_spot_only(session: AsyncSession, content_id: str) -> None:
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, first_image_url, show_flag) "
            "VALUES (:cid, 12, :t, 'http://kto.example/i.jpg', 1) "
            "ON CONFLICT (content_id) DO NOTHING"
        ),
        {"cid": content_id, "t": f"t-{content_id}"},
    )
    await session.commit()


async def _insert_embedding(session: AsyncSession, content_id: str, seed: int) -> None:
    rng = random.Random(seed)
    raw = [rng.gauss(0, 1) for _ in range(512)]
    norm = math.sqrt(sum(x * x for x in raw))
    vec = [x / norm for x in raw]
    literal = "[" + ",".join(f"{v:.6f}" for v in vec) + "]"
    await session.execute(
        text(
            "INSERT INTO spot_embeddings (content_id, embedding) "
            "VALUES (:cid, (:emb)::halfvec(512)) "
            "ON CONFLICT (content_id) DO NOTHING"
        ),
        {"cid": content_id, "emb": literal},
    )
    await session.commit()


@pytest.mark.asyncio
async def test_mood_spots_returns_envelope_with_data(
    client: AsyncClient,
    override_db_and_seed: AsyncSession,
) -> None:
    seed = override_db_and_seed
    await _insert_spot_with_mood(seed, "rt_s1", "sea")
    await _insert_spot_with_mood(seed, "rt_s2", "sea")

    resp = await client.get("/v1/moods/sea/spots?limit=10000")

    assert resp.status_code == 200
    body = resp.json()
    assert body["error"] is None
    cids = {item["contentId"] for item in body["data"]}
    assert {"rt_s1", "rt_s2"}.issubset(cids)


@pytest.mark.asyncio
async def test_mood_spots_returns_404_for_unknown_mood(client: AsyncClient) -> None:
    resp = await client.get("/v1/moods/zzz/spots")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


@pytest.mark.asyncio
async def test_similar_route_returns_query_and_neighbors(
    client: AsyncClient,
    override_db_and_seed: AsyncSession,
) -> None:
    seed = override_db_and_seed
    for cid in ("rt_q", "rt_dup"):
        await _insert_spot_only(seed, cid)
    await _insert_embedding(seed, "rt_q", seed=1)
    await _insert_embedding(seed, "rt_dup", seed=1)

    resp = await client.get("/v1/spots/rt_q/similar?limit=5")

    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["query"]["contentId"] == "rt_q"
    neighbor_ids = [n["contentId"] for n in body["data"]["neighbors"]]
    assert "rt_q" not in neighbor_ids
    assert neighbor_ids[0] == "rt_dup"


@pytest.mark.asyncio
async def test_similar_route_returns_404_for_unknown_spot(client: AsyncClient) -> None:
    resp = await client.get("/v1/spots/ghost-xxx-rt/similar")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
