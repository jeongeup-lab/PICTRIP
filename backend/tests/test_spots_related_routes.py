"""Integration test for GET /v1/spots/{id}/related (ADR-0005/0015).

The route depends on KtoDep + RedisDep, neither of which is lifespan-installed
in tests, so the fixture overrides get_kto (a canned FakeKto) and get_redis
(in-memory FakeRedis) alongside the usual savepoint-isolated get_db.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
import pytest_asyncio
from fakeredis.aioredis import FakeRedis
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.main import app


class FakeKto:
    async def call(self, service: Any, operation: str, **params: Any) -> list[dict[str, Any]]:
        return [
            {
                "tAtsNm": "테스트관광지",
                "rlteTatsNm": "춘천향교",
                "rlteRank": "1",
                "rlteCtgryMclsNm": "관광지",
                "rlteRegnNm": "강원특별자치도",
                "rlteSignguNm": "춘천시",
                "rlteBsicAdres": "강원특별자치도 춘천시 어딘가",
            }
        ]


@pytest_asyncio.fixture(autouse=True)
async def overrides() -> AsyncIterator[AsyncSession]:
    from app.core.db import get_db
    from app.core.kto_client import get_kto
    from app.core.redis import get_redis

    eng = create_async_engine(str(settings.sqlalchemy_database_url), poolclass=NullPool)
    fake_redis = FakeRedis(decode_responses=False)
    async with eng.connect() as conn:
        tx = await conn.begin()
        try:
            seed = AsyncSession(
                bind=conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
            )

            async def _override_db() -> AsyncIterator[AsyncSession]:
                session = AsyncSession(
                    bind=conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
                )
                try:
                    yield session
                finally:
                    await session.close()

            app.dependency_overrides[get_db] = _override_db
            app.dependency_overrides[get_kto] = lambda: FakeKto()
            app.dependency_overrides[get_redis] = lambda: fake_redis
            try:
                yield seed
            finally:
                await seed.close()
                app.dependency_overrides.clear()
        finally:
            if tx.is_active:
                await tx.rollback()
    await eng.dispose()
    await fake_redis.aclose()


async def _seed_spot(session: AsyncSession, content_id: str, title: str) -> None:
    await session.execute(
        text(
            "INSERT INTO sigungus (ldong_signgu_cd, ldong_regn_cd, ldong_signgu_nm) "
            "VALUES ('51110', '51', '춘천시') ON CONFLICT (ldong_signgu_cd) DO NOTHING"
        )
    )
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, show_flag, "
            "ldong_regn_cd, ldong_signgu_cd) VALUES (:cid, 12, :t, 1, '51', '51110') "
            "ON CONFLICT (content_id) DO NOTHING"
        ),
        {"cid": content_id, "t": title},
    )
    await session.commit()


@pytest.mark.asyncio
async def test_related_returns_chips(client: AsyncClient, overrides: AsyncSession) -> None:
    seed = overrides
    await _seed_spot(seed, "relr_q", "테스트관광지")
    await _seed_spot(seed, "relr_hyang", "춘천향교")

    resp = await client.get("/v1/spots/relr_q/related")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    chip = data[0]
    assert chip["name"] == "춘천향교"
    assert chip["contentId"] == "relr_hyang"  # resolved → deep-linkable chip
    assert chip["address"] == "강원특별자치도 춘천시 어딘가"
    assert chip["regionName"] == "강원특별자치도 춘천시"


@pytest.mark.asyncio
async def test_related_unknown_spot_is_404(client: AsyncClient, overrides: AsyncSession) -> None:
    resp = await client.get("/v1/spots/ghost/related")
    assert resp.status_code == 404
