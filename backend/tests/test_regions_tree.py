"""GET /v1/map/regions-tree — 17 sido + sigungus, runtime-AVG centroid, 24h cache."""

from __future__ import annotations

import json

from fakeredis.aioredis import FakeRedis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.redis import get_redis
from app.main import app
from app.modules.map.services import REGIONS_TREE_KEY, regions_tree


async def _seed_region(session: AsyncSession, code: str, name: str) -> None:
    await session.execute(
        text(
            "INSERT INTO regions (ldong_regn_cd, ldong_regn_nm) VALUES (:c, :n) "
            "ON CONFLICT DO NOTHING"
        ),
        {"c": code, "n": name},
    )


async def _seed_sigungu(session: AsyncSession, code: str, regn: str, name: str) -> None:
    await session.execute(
        text(
            "INSERT INTO sigungus (ldong_signgu_cd, ldong_regn_cd, ldong_signgu_nm) "
            "VALUES (:c, :r, :n) ON CONFLICT DO NOTHING"
        ),
        {"c": code, "r": regn, "n": name},
    )


async def _seed_spot(
    session: AsyncSession,
    cid: str,
    *,
    regn: str,
    signgu: str | None,
    lat: float,
    lng: float,
    show: int = 1,
) -> None:
    # mapx = lng, mapy = lat (S07 ERD).
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, show_flag, "
            "mapx, mapy, ldong_regn_cd, ldong_signgu_cd) "
            "VALUES (:cid, 12, :t, :show, :lng, :lat, :regn, :signgu)"
        ),
        {
            "cid": cid,
            "t": f"t-{cid}",
            "show": show,
            "lng": lng,
            "lat": lat,
            "regn": regn,
            "signgu": signgu,
        },
    )


async def _seed_basic(session: AsyncSession) -> None:
    """1 region + 2 sigungus; one sigungu has spots, one is empty."""
    await _seed_region(session, "11", "서울특별시")
    await _seed_sigungu(session, "1101", "11", "종로구")
    await _seed_sigungu(session, "1102", "11", "강남구")
    # 종로구: two spots → AVG
    await _seed_spot(session, "s1", regn="11", signgu="1101", lat=37.50, lng=127.00)
    await _seed_spot(session, "s2", regn="11", signgu="1101", lat=37.60, lng=127.10)
    # 강남구: no spots → falls back to sido centroid
    # hidden spot must not move the centroid
    await _seed_spot(session, "s3", regn="11", signgu="1101", lat=99.0, lng=99.0, show=0)


# --------------------------------------------------------------------------- #
# Service
# --------------------------------------------------------------------------- #
async def test_centroid_is_runtime_avg(db_session: AsyncSession) -> None:
    redis = FakeRedis(decode_responses=True)
    await _seed_basic(db_session)

    tree = await regions_tree(db_session, redis)
    seoul = next(r for r in tree if r["regionCode"] == "11")
    assert seoul["regionName"] == "서울특별시"
    # sido centroid = AVG over both visible spots (hidden excluded)
    assert seoul["centroid"]["lat"] == 37.55
    assert seoul["centroid"]["lng"] == 127.05

    jongno = next(s for s in seoul["sigungus"] if s["sigunguCode"] == "1101")
    assert jongno["centroid"]["lat"] == 37.55
    assert jongno["centroid"]["lng"] == 127.05


async def test_empty_sigungu_falls_back_to_sido_centroid(db_session: AsyncSession) -> None:
    redis = FakeRedis(decode_responses=True)
    await _seed_basic(db_session)

    tree = await regions_tree(db_session, redis)
    seoul = next(r for r in tree if r["regionCode"] == "11")
    gangnam = next(s for s in seoul["sigungus"] if s["sigunguCode"] == "1102")
    # 강남구 has no spots → COALESCE to sido centroid
    assert gangnam["centroid"]["lat"] == seoul["centroid"]["lat"]
    assert gangnam["centroid"]["lng"] == seoul["centroid"]["lng"]


async def test_serves_from_cache_when_present(db_session: AsyncSession) -> None:
    redis = FakeRedis(decode_responses=True)
    cached = [
        {
            "regionCode": "ZZ",
            "regionName": "캐시",
            "centroid": {"lat": 1.0, "lng": 2.0},
            "sigungus": [],
        }
    ]
    await redis.set(REGIONS_TREE_KEY, json.dumps(cached))

    # DB has nothing seeded → if cache is honoured we still get the cached tree.
    tree = await regions_tree(db_session, redis)
    assert tree == cached


async def test_caches_assembled_tree_24h(db_session: AsyncSession) -> None:
    redis = FakeRedis(decode_responses=True)
    await _seed_basic(db_session)

    await regions_tree(db_session, redis)
    raw = await redis.get(REGIONS_TREE_KEY)
    assert raw is not None
    ttl = await redis.ttl(REGIONS_TREE_KEY)
    assert 86_000 < ttl <= 86_400


# --------------------------------------------------------------------------- #
# Route
# --------------------------------------------------------------------------- #
async def test_regions_tree_route(db_session: AsyncSession, client) -> None:
    redis = FakeRedis(decode_responses=True)
    await _seed_basic(db_session)

    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_redis] = lambda: redis
    try:
        resp = await client.get("/v1/map/regions-tree")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert isinstance(data, list) and data
    seoul = next(r for r in data if r["regionCode"] == "11")
    assert isinstance(seoul["centroid"]["lat"], float)
    assert isinstance(seoul["centroid"]["lng"], float)
    assert seoul["sigungus"]
