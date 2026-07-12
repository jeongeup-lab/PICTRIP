from __future__ import annotations

from dataclasses import dataclass

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.redis import get_redis
from app.main import app

_DIM = 512


def _literal(vec: list[float]) -> str:
    return "[" + ",".join(f"{v:.6f}" for v in vec) + "]"


_CLOSE = [0.1] * _DIM
_FAR = [0.1 if i % 2 == 0 else -0.1 for i in range(_DIM)]


@pytest.fixture(autouse=True)
def _wire(db_session, redis_client_fake):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_redis] = lambda: redis_client_fake
    yield
    app.dependency_overrides.clear()


async def _insert_overseas(session: AsyncSession, *, embedding: list[float] | None) -> int:
    row = (
        await session.execute(
            text(
                "INSERT INTO overseas_spots (wikidata_id, name_ko, country_code, "
                "country_name_ko, image_url, image_source_url, embedding) "
                "VALUES (:qid, :name, 'FR', '프랑스', 'https://img/x', 'https://src/x', "
                "CAST(:emb AS halfvec(512))) RETURNING id"
            ),
            {
                "qid": f"Q{id(session) % 100000}{'e' if embedding else 'n'}",
                "name": "해외명소",
                "emb": _literal(embedding) if embedding is not None else None,
            },
        )
    ).scalar_one()
    await session.commit()
    return int(row)


async def _insert_spot(
    session: AsyncSession, content_id: str, vec: list[float], *, overview: str | None
) -> None:
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, first_image_url, "
            "addr1, mapx, mapy, show_flag) "
            "VALUES (:cid, 12, :t, 'http://kto/p.jpg', 'addr1', 127.0, 37.0, 1) "
            "ON CONFLICT (content_id) DO NOTHING"
        ),
        {"cid": content_id, "t": f"title-{content_id}"},
    )
    await session.execute(
        text(
            "INSERT INTO spot_embeddings (content_id, embedding) "
            "VALUES (:cid, CAST(:emb AS halfvec(512))) ON CONFLICT (content_id) DO NOTHING"
        ),
        {"cid": content_id, "emb": _literal(vec)},
    )
    if overview is not None:
        await session.execute(
            text(
                "INSERT INTO spot_details (content_id, content_type_id, overview) "
                "VALUES (:cid, 12, :ov) ON CONFLICT (content_id) DO NOTHING"
            ),
            {"cid": content_id, "ov": overview},
        )
    await session.commit()


@dataclass
class Seeded:
    overseas_id: int


@pytest.fixture
async def seeded_matching(db_session) -> Seeded:
    oid = await _insert_overseas(db_session, embedding=_CLOSE)
    await _insert_spot(db_session, "mt_a", _CLOSE, overview="첫 문장이다. 둘째 문장.")
    await _insert_spot(db_session, "mt_b", _CLOSE, overview="다른 소개문이다.")
    return Seeded(overseas_id=oid)


@pytest.fixture
async def seeded_matching_far(db_session) -> Seeded:
    oid = await _insert_overseas(db_session, embedding=_CLOSE)
    await _insert_spot(db_session, "mt_far_a", _FAR, overview="멀리 있다.")
    await _insert_spot(db_session, "mt_far_b", _FAR, overview="멀리 있다 둘.")
    return Seeded(overseas_id=oid)


@pytest.fixture
async def seeded_overseas_no_embedding(db_session) -> int:
    return await _insert_overseas(db_session, embedding=None)


async def test_matches_returns_similar_domestic(client, seeded_matching):
    res = await client.get(f"/v1/overseas/{seeded_matching.overseas_id}/matches")
    body = res.json()
    assert res.status_code == 200 and body["error"] is None
    matches = body["data"]["matches"]
    assert 1 <= len(matches) <= 3
    assert {"contentId", "title", "regionLabel", "imageUrl", "overviewFirst"} <= set(matches[0])


async def test_matches_threshold_filters_far_spots(client, seeded_matching_far):
    res = await client.get(f"/v1/overseas/{seeded_matching_far.overseas_id}/matches")
    assert res.json()["data"]["matches"] == []


async def test_matches_cached_in_redis(client, seeded_matching, redis_client_fake):
    await client.get(f"/v1/overseas/{seeded_matching.overseas_id}/matches")
    assert await redis_client_fake.get(f"match:{seeded_matching.overseas_id}") is not None


async def test_matches_unknown_id_404(client):
    res = await client.get("/v1/overseas/999999/matches")
    assert res.status_code == 404 and res.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


async def test_matches_without_embedding_returns_empty(client, seeded_overseas_no_embedding):
    res = await client.get(f"/v1/overseas/{seeded_overseas_no_embedding}/matches")
    assert res.json()["data"]["matches"] == []
