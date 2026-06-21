"""CRS course-draft service + route tests.

POST /courses/draft produces 3 candidate courses (efficient / mood / calm)
from a base spot. Drafts are computed on the fly — no persistence — so the
tests assert deterministic orderings, not DB rows.

Seeding mirrors tests/test_spt_discover_routes.py: a base spot + embedding
neighbors with controlled geography so each strategy's ordering is checkable.
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
from app.core.exceptions import ResourceNotFound
from app.main import app
from app.modules.courses.services import STRATEGIES, build_draft_courses


async def _insert_spot(
    session: AsyncSession,
    content_id: str,
    *,
    mapx: float | None = None,
    mapy: float | None = None,
) -> None:
    await session.execute(
        text(
            "INSERT INTO spots "
            "(content_id, content_type_id, title, first_image_url, addr1, mapx, mapy, show_flag) "
            "VALUES (:cid, 12, :t, 'http://kto.example/i.jpg', :a, :x, :y, 1) "
            "ON CONFLICT (content_id) DO NOTHING"
        ),
        {
            "cid": content_id,
            "t": f"title-{content_id}",
            "a": f"addr-{content_id}",
            "x": mapx,
            "y": mapy,
        },
    )


def _unit_vec(seed: int, dim: int = 512) -> list[float]:
    rng = random.Random(seed)
    raw = [rng.gauss(0, 1) for _ in range(dim)]
    norm = math.sqrt(sum(x * x for x in raw))
    return [x / norm for x in raw]


async def _insert_embedding(session: AsyncSession, content_id: str, vec: list[float]) -> None:
    literal = "[" + ",".join(f"{v:.6f}" for v in vec) + "]"
    await session.execute(
        text(
            "INSERT INTO spot_embeddings (content_id, embedding) "
            "VALUES (:cid, (:emb)::halfvec(512)) "
            "ON CONFLICT (content_id) DO NOTHING"
        ),
        {"cid": content_id, "emb": literal},
    )


async def _seed_base_with_neighbors(session: AsyncSession, prefix: str) -> str:
    """Base spot + 4 neighbors. Embeddings are near-identical so all are
    candidates; geography is spread so efficient/calm differ from mood.
    """
    base_id = f"{prefix}_base"
    await _insert_spot(session, base_id, mapx=127.0, mapy=37.0)
    base_vec = _unit_vec(1)
    await _insert_embedding(session, base_id, base_vec)

    # Neighbors placed at increasing geographic distance from base, but with
    # embedding distance INVERTED relative to geography so the three strategies
    # cannot collapse into the same order.
    coords = {
        f"{prefix}_n1": (127.1, 37.0),  # closest geographically
        f"{prefix}_n2": (127.3, 37.0),
        f"{prefix}_n3": (127.6, 37.0),
        f"{prefix}_n4": (128.0, 37.0),  # farthest geographically
    }
    for i, (cid, (x, y)) in enumerate(coords.items()):
        await _insert_spot(session, cid, mapx=x, mapy=y)
        # Perturb embedding slightly; farther-geo spots get closer embeddings.
        vec = base_vec[:]
        vec[i] += 0.02 * (4 - i)
        n = math.sqrt(sum(v * v for v in vec))
        await _insert_embedding(session, cid, [v / n for v in vec])
    return base_id


# --- service unit tests -------------------------------------------------------


@pytest.mark.asyncio
async def test_build_draft_returns_three_distinct_strategies(db_session: AsyncSession) -> None:
    base_id = await _seed_base_with_neighbors(db_session, "svc1")
    courses = await build_draft_courses(
        db_session,
        base_content_id=base_id,
        duration="1n2d",
        pace="normal",
        companion="couple",
    )
    assert len(courses) == 3
    assert [c.strategy for c in courses] == list(STRATEGIES)
    for c in courses:
        assert c.items, f"{c.strategy} has no items"
        # base spot always leads the itinerary
        assert c.items[0].content_id == base_id


@pytest.mark.asyncio
async def test_build_draft_is_deterministic(db_session: AsyncSession) -> None:
    base_id = await _seed_base_with_neighbors(db_session, "svc2")
    a = await build_draft_courses(
        db_session, base_content_id=base_id, duration="1n2d", pace="normal", companion="solo"
    )
    b = await build_draft_courses(
        db_session, base_content_id=base_id, duration="1n2d", pace="normal", companion="solo"
    )
    order_a = [[i.content_id for i in c.items] for c in a]
    order_b = [[i.content_id for i in c.items] for c in b]
    assert order_a == order_b


@pytest.mark.asyncio
async def test_efficient_orders_by_geographic_proximity(db_session: AsyncSession) -> None:
    base_id = await _seed_base_with_neighbors(db_session, "svc3")
    courses = await build_draft_courses(
        db_session, base_content_id=base_id, duration="2n3d", pace="normal", companion="friends"
    )
    eff = next(c for c in courses if c.strategy == "efficient")
    ids = [i.content_id for i in eff.items]
    # nearest-neighbor greedy from base => n1, n2, n3, n4 by ascending distance
    assert ids == [base_id, "svc3_n1", "svc3_n2", "svc3_n3", "svc3_n4"]


@pytest.mark.asyncio
async def test_mood_orders_by_embedding_similarity(db_session: AsyncSession) -> None:
    base_id = await _seed_base_with_neighbors(db_session, "svc4")
    courses = await build_draft_courses(
        db_session, base_content_id=base_id, duration="2n3d", pace="normal", companion="family"
    )
    mood = next(c for c in courses if c.strategy == "mood")
    ids = [i.content_id for i in mood.items]
    # embedding was inverted vs geography: n4 closest, n1 farthest
    assert ids == [base_id, "svc4_n4", "svc4_n3", "svc4_n2", "svc4_n1"]


@pytest.mark.asyncio
async def test_calm_has_fewer_stops(db_session: AsyncSession) -> None:
    base_id = await _seed_base_with_neighbors(db_session, "svc5")
    # 'day' => full 4 stops (base + 3), calm trims to 2; 4 neighbors are seeded
    # so the candidate pool exceeds calm's cap and the trim is observable.
    courses = await build_draft_courses(
        db_session, base_content_id=base_id, duration="day", pace="normal", companion="solo"
    )
    by = {c.strategy: c for c in courses}
    assert len(by["calm"].items) < len(by["efficient"].items)
    assert len(by["calm"].items) >= 1


@pytest.mark.asyncio
async def test_build_draft_raises_for_unknown_base(db_session: AsyncSession) -> None:
    with pytest.raises(ResourceNotFound):
        await build_draft_courses(
            db_session,
            base_content_id="crs-ghost-not-real",
            duration="day",
            pace="normal",
            companion="solo",
        )


# --- route integration test ---------------------------------------------------


@pytest_asyncio.fixture
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


@pytest.mark.asyncio
async def test_draft_route_returns_three_courses(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    seed = override_db_and_seed
    base_id = await _seed_base_with_neighbors(seed, "rt1")
    await seed.commit()

    resp = await client.post(
        "/v1/courses/draft",
        json={
            "baseContentId": base_id,
            "duration": "1n2d",
            "pace": "normal",
            "companion": "couple",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["error"] is None
    assert body["meta"]["traceId"] is not None
    courses = body["data"]["courses"]
    assert len(courses) == 3
    assert {c["strategy"] for c in courses} == set(STRATEGIES)
    for c in courses:
        assert c["items"], f"{c['strategy']} empty"
        # spot card contract: same field names as SPT SpotCard
        first = c["items"][0]
        assert set(first) >= {"contentId", "title", "firstImageUrl", "addr1", "mapx", "mapy"}
        assert first["contentId"] == base_id


@pytest.mark.asyncio
async def test_draft_route_deterministic_across_calls(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    seed = override_db_and_seed
    base_id = await _seed_base_with_neighbors(seed, "rt2")
    await seed.commit()

    payload = {
        "baseContentId": base_id,
        "duration": "2n3d",
        "pace": "packed",
        "companion": "friends",
    }
    r1 = await client.post("/v1/courses/draft", json=payload)
    r2 = await client.post("/v1/courses/draft", json=payload)
    assert r1.status_code == r2.status_code == 200

    def _orders(body: dict) -> list[list[str]]:
        return [[i["contentId"] for i in c["items"]] for c in body["data"]["courses"]]

    assert _orders(r1.json()) == _orders(r2.json())


@pytest.mark.asyncio
async def test_draft_route_404_for_unknown_base(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    resp = await client.post(
        "/v1/courses/draft",
        json={
            "baseContentId": "rt-ghost-xxx",
            "duration": "day",
            "pace": "normal",
            "companion": "solo",
        },
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
