"""Integration tests for GET /v1/spots/{contentId}."""

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
from app.core.kto_client import get_kto
from app.core.redis import get_redis
from app.main import app


class FakeKto:
    def __init__(self, common, images, intro=None) -> None:
        self._common = common
        self._images = images
        self._intro = intro if intro is not None else []

    async def call(self, service, operation, **params):
        if operation == "detailCommon2":
            return self._common
        if operation == "detailImage2":
            return self._images
        if operation == "detailIntro2":
            return self._intro
        return []


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


@pytest.fixture(autouse=True)
def override_kto() -> AsyncIterator[None]:
    app.dependency_overrides[get_kto] = lambda: FakeKto(
        [{"overview": "상세 설명", "homepage": "<a>hp</a>", "tel": "02-1"}],
        [{"originimgurl": "http://kto/1.jpg", "smallimageurl": "http://kto/1s.jpg"}],
    )
    yield
    app.dependency_overrides.pop(get_kto, None)


@pytest.fixture(autouse=True)
def override_redis() -> AsyncIterator[None]:
    fake = FakeRedis(decode_responses=True)
    app.dependency_overrides[get_redis] = lambda: fake
    yield
    app.dependency_overrides.pop(get_redis, None)


async def _insert_spot(session: AsyncSession, content_id: str) -> None:
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, first_image_url, addr1, show_flag) "
            "VALUES (:cid, 12, :t, 'http://kto/first.jpg', 'addr1', 1) "
            "ON CONFLICT (content_id) DO NOTHING"
        ),
        {"cid": content_id, "t": f"title-{content_id}"},
    )
    await session.commit()


@pytest.mark.asyncio
async def test_detail_returns_envelope(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    await _insert_spot(override_db_and_seed, "RT-DETAIL")

    resp = await client.get("/v1/spots/RT-DETAIL")

    assert resp.status_code == 200
    body = resp.json()
    assert body["error"] is None
    data = body["data"]
    assert data["contentId"] == "RT-DETAIL"
    assert data["overview"] == "상세 설명"
    assert data["detailStatus"] == "fresh"
    assert data["images"][0]["originImageUrl"] == "http://kto/1.jpg"
    assert "moods" not in data
    assert "detailStatus" in data
    assert "congestion" in data
    assert {"contentId", "title", "addr1", "regionName", "images"} <= set(data)


@pytest.mark.asyncio
async def test_detail_404_for_unknown(client: AsyncClient) -> None:
    resp = await client.get("/v1/spots/ghost-rt-detail")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


@pytest.mark.asyncio
async def test_detail_route_exposes_intro_and_category(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    # Re-override KTO so detailIntro2 returns a usetime intro.
    app.dependency_overrides[get_kto] = lambda: FakeKto(
        [{"overview": "상세 설명", "homepage": "<a>hp</a>", "tel": "02-1"}],
        [{"originimgurl": "http://kto/1.jpg", "smallimageurl": "http://kto/1s.jpg"}],
        [{"usetime": "09:30~17:30"}],
    )

    # Seed a spot whose lcls_systm3 maps to '사적지'.
    await override_db_and_seed.execute(
        text(
            "INSERT INTO lcls_systm_codes "
            "(lcls_systm3_cd, lcls_systm2_cd, lcls_systm1_cd, "
            " lcls_systm3_nm, lcls_systm2_nm, lcls_systm1_nm) "
            "VALUES ('HS010100','HS01','HS','사적지','역사유적지','역사관광') "
            "ON CONFLICT DO NOTHING"
        )
    )
    await _insert_spot(override_db_and_seed, "DT-RT-INTRO")
    await override_db_and_seed.execute(
        text("UPDATE spots SET lcls_systm3 = 'HS010100' WHERE content_id = 'DT-RT-INTRO'")
    )
    await override_db_and_seed.commit()

    resp = await client.get("/v1/spots/DT-RT-INTRO")

    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["category"] == "사적지"
    assert body["data"]["intro"]["usetime"] == "09:30~17:30"
