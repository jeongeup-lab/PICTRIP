"""Integration tests for the moods list route.

  GET /v1/moods  — the 8 moods + per-mood spotsCount (#6 무드 탭 "N곳")

spotsCount counts active, image-bearing spots tagged with the mood — the same
predicate ``GET /v1/moods/{code}/spots`` uses — so the cover count matches the
collection. The 8 moods are seeded by migration 0001; the test DB starts with no
spots, so seeded counts are exact. Pattern mirrors test_spt_discover_routes.py.
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


async def _seed_spot_with_mood(
    session: AsyncSession,
    *,
    content_id: str,
    mood_code: str,
    show_flag: int = 1,
    has_image: bool = True,
) -> None:
    image = "'http://kto.example/i.jpg'" if has_image else "NULL"
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, first_image_url, show_flag) "
            f"VALUES (:cid, 12, :t, {image}, :sf) "
            "ON CONFLICT (content_id) DO NOTHING"
        ),
        {"cid": content_id, "t": f"title-{content_id}", "sf": show_flag},
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
async def test_moods_list_shape(client: AsyncClient) -> None:
    resp = await client.get("/v1/moods")

    assert resp.status_code == 200
    body = resp.json()
    assert body["error"] is None
    data = body["data"]
    assert len(data) == 8
    first = data[0]
    assert set(first) == {"code", "name", "emoji", "sortOrder", "spotsCount"}
    assert isinstance(first["spotsCount"], int)
    # ordered by sortOrder
    assert [m["sortOrder"] for m in data] == sorted(m["sortOrder"] for m in data)


@pytest.mark.asyncio
async def test_moods_spots_count_matches_active_image_bearing_spots(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    s = override_db_and_seed
    await _seed_spot_with_mood(s, content_id="MC-1", mood_code="sea")
    await _seed_spot_with_mood(s, content_id="MC-2", mood_code="sea")
    await _seed_spot_with_mood(s, content_id="MC-3", mood_code="sea", show_flag=0)  # hidden
    await _seed_spot_with_mood(s, content_id="MC-4", mood_code="sea", has_image=False)  # no image
    await _seed_spot_with_mood(s, content_id="MC-5", mood_code="mountain")

    resp = await client.get("/v1/moods")
    counts = {m["code"]: m["spotsCount"] for m in resp.json()["data"]}

    assert counts["sea"] == 2  # hidden + image-less excluded
    assert counts["mountain"] == 1
    assert counts["lake"] == 0
