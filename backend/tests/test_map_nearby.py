"""GET /v1/map/nearby — DB 쿼리(spots) + Haversine + 카테고리 + crowd merge."""

from __future__ import annotations

import json

import pytest
from fakeredis.aioredis import FakeRedis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.redis import get_redis
from app.main import app
from app.modules.map.services import CrowdRow, NearbySpotRow, merge_crowd, nearby_spots
from app.modules.spots.services import NearbyCategory

# 광화문 근처 기준점
LAT, LNG = 37.5759, 126.9769


async def _seed(
    session: AsyncSession,
    cid: str,
    *,
    lat: float,
    lng: float,
    l1="HS",
    l2=None,
    l3=None,
    show=1,
    img="http://kto/i.jpg",
    img2="http://kto/i2.jpg",
    overview=None,
) -> None:
    if l3 is not None:
        # spots.lcls_systm3 → lcls_systm_codes FK
        await session.execute(
            text(
                "INSERT INTO lcls_systm_codes (lcls_systm3_cd, lcls_systm2_cd, lcls_systm1_cd, "
                "lcls_systm3_nm) VALUES (:l3, :l2, :l1, :l3) ON CONFLICT DO NOTHING"
            ),
            {"l3": l3, "l2": l2, "l1": l1},
        )
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, first_image_url, "
            "first_image2_url, show_flag, mapx, mapy, lcls_systm1, lcls_systm2, lcls_systm3) "
            "VALUES (:cid, 12, :t, :img, :img2, :show, :lng, :lat, :l1, :l2, :l3)"
        ),
        {
            "cid": cid,
            "t": f"t-{cid}",
            "img": img,
            "img2": img2,
            "show": show,
            "lng": lng,
            "lat": lat,
            "l1": l1,
            "l2": l2,
            "l3": l3,
        },
    )
    if overview is not None:
        # overview는 spot_details에만 산다(ADR-0007) — nearby의 LEFT JOIN 검증용.
        await session.execute(
            text(
                "INSERT INTO spot_details (content_id, content_type_id, overview) "
                "VALUES (:cid, 12, :ov)"
            ),
            {"cid": cid, "ov": overview},
        )


# --------------------------------------------------------------------------- #
# Unit: merge_crowd (pure function)
# --------------------------------------------------------------------------- #
def _row(cid: str) -> NearbySpotRow:
    return NearbySpotRow(
        content_id=cid,
        title="t",
        first_image_url=None,
        first_image2_url=None,
        addr1=None,
        mapx=1.0,
        mapy=2.0,
        dist=100.0,
    )


def test_merge_crowd_attaches_when_present() -> None:
    spots = [_row("A"), _row("B")]
    crowd = {"A": CrowdRow(rate=0.8, level="crowded")}
    merged = merge_crowd(spots, crowd)
    assert merged[0].crowd is not None
    assert merged[0].crowd.level == "crowded"
    assert merged[0].crowd.rate == 0.8
    # B has no crowd row -> graceful None, not an error.
    assert merged[1].crowd is None


def test_merge_crowd_empty_lookup_is_graceful() -> None:
    merged = merge_crowd([_row("A")], {})
    assert merged[0].crowd is None


# --------------------------------------------------------------------------- #
# Service: DB query (bbox + haversine + category + crowd)
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_orders_by_distance_and_applies_radius(db_session: AsyncSession) -> None:
    redis = FakeRedis(decode_responses=False)
    await _seed(db_session, "near", lat=LAT + 0.001, lng=LNG)  # ~110m
    await _seed(db_session, "mid", lat=LAT + 0.005, lng=LNG)  # ~550m
    await _seed(db_session, "far", lat=LAT + 0.05, lng=LNG)  # ~5.5km (밖)

    rows = await nearby_spots(db_session, redis, lat=LAT, lng=LNG, radius=1000, category=None)
    ids = [r.content_id for r in rows]
    assert ids[:2] == ["near", "mid"]  # 거리순
    assert "far" not in ids  # radius 밖 제외
    assert rows[0].dist is not None and rows[1].dist is not None
    assert rows[0].dist < rows[1].dist


@pytest.mark.asyncio
async def test_excludes_hidden_and_imageless(db_session: AsyncSession) -> None:
    redis = FakeRedis(decode_responses=False)
    await _seed(db_session, "hidden", lat=LAT, lng=LNG, show=0)
    await _seed(db_session, "noimg", lat=LAT, lng=LNG, img=None)
    await _seed(db_session, "ok", lat=LAT, lng=LNG)

    rows = await nearby_spots(db_session, redis, lat=LAT, lng=LNG, radius=1000, category=None)
    ids = {r.content_id for r in rows}
    assert ids == {"ok"}


@pytest.mark.asyncio
async def test_category_filter_food_excludes_bakery(db_session: AsyncSession) -> None:
    redis = FakeRedis(decode_responses=False)
    await _seed(db_session, "rest", lat=LAT, lng=LNG, l1="FD", l2="FD01", l3="FD010100")
    await _seed(db_session, "bakery", lat=LAT, lng=LNG, l1="FD", l2="FD03", l3="FD030100")

    rows = await nearby_spots(
        db_session, redis, lat=LAT, lng=LNG, radius=1000, category=NearbyCategory.food
    )
    ids = {r.content_id for r in rows}
    assert ids == {"rest"}  # 제과(FD030100)는 food 아님


@pytest.mark.asyncio
async def test_no_category_restricts_to_defined_taxonomy(db_session: AsyncSession) -> None:
    # '전체'(category=None)는 무필터가 아니라 정의된 5개 카테고리의 union.
    redis = FakeRedis(decode_responses=False)
    await _seed(db_session, "spot", lat=LAT, lng=LNG, l1="NA")  # attraction
    await _seed(db_session, "uncat", lat=LAT, lng=LNG, l1="A0")  # 어느 칩에도 안 잡힘

    rows = await nearby_spots(db_session, redis, lat=LAT, lng=LNG, radius=1000, category=None)
    ids = {r.content_id for r in rows}
    assert ids == {"spot"}  # 미분류(A0)는 전체 뷰에서도 제외


@pytest.mark.asyncio
async def test_derived_category_and_image2_passthrough(db_session: AsyncSession) -> None:
    redis = FakeRedis(decode_responses=False)
    await _seed(db_session, "cafe1", lat=LAT, lng=LNG, l1="FD", l2="FD05", l3="FD050100")

    rows = await nearby_spots(db_session, redis, lat=LAT, lng=LNG, radius=1000, category=None)
    row = next(r for r in rows if r.content_id == "cafe1")
    assert row.category == "cafe"
    assert row.first_image2_url == "http://kto/i2.jpg"  # raw — https 업그레이드는 스키마 validator


@pytest.mark.asyncio
async def test_overview_left_join_passthrough(db_session: AsyncSession) -> None:
    # spot_details.overview가 있으면 카드에 verbatim으로 실린다; 없으면 None(LEFT JOIN).
    redis = FakeRedis(decode_responses=False)
    await _seed(db_session, "withov", lat=LAT, lng=LNG, overview="40년대 지어진 한옥 카페")
    await _seed(db_session, "noov", lat=LAT, lng=LNG)

    rows = await nearby_spots(db_session, redis, lat=LAT, lng=LNG, radius=1000, category=None)
    by_id = {r.content_id: r for r in rows}
    assert by_id["withov"].overview == "40년대 지어진 한옥 카페"  # verbatim
    assert by_id["noov"].overview is None  # 캐시 전 → None, 에러 아님


@pytest.mark.asyncio
async def test_crowd_merge(db_session: AsyncSession) -> None:
    redis = FakeRedis(decode_responses=False)
    await _seed(db_session, "c1", lat=LAT, lng=LNG)
    await redis.set("crowd:c1", json.dumps({"rate": 0.4, "level": "normal"}))

    rows = await nearby_spots(db_session, redis, lat=LAT, lng=LNG, radius=1000, category=None)
    row = next(r for r in rows if r.content_id == "c1")
    assert row.crowd is not None and row.crowd.level == "normal"


# --------------------------------------------------------------------------- #
# Route: /v1/map/nearby
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_nearby_route_returns_new_fields(db_session, client):
    redis = FakeRedis(decode_responses=False)
    # https 업그레이드는 KTO 호스트(tong.visitkorea.or.kr)에만 적용된다 — 실제 호스트로 시드.
    await _seed(
        db_session,
        "rt1",
        lat=LAT,
        lng=LNG,
        l1="FD",
        l2="FD05",
        l3="FD050100",
        img2="http://tong.visitkorea.or.kr/i2.jpg",
    )

    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_redis] = lambda: redis
    try:
        resp = await client.get("/v1/map/nearby", params={"lat": LAT, "lng": LNG, "radius": 1000})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    item = next(i for i in body["data"] if i["contentId"] == "rt1")
    assert item["category"] == "cafe"
    # http→https 업그레이드(validator, KTO 호스트만)
    assert item["firstImage2Url"] == "https://tong.visitkorea.or.kr/i2.jpg"
    assert "dist" in item


@pytest.mark.asyncio
async def test_nearby_route_category_param(db_session, client):
    redis = FakeRedis(decode_responses=False)
    await _seed(db_session, "shop", lat=LAT, lng=LNG, l1="SH", l2="SH01")
    await _seed(db_session, "cafe2", lat=LAT, lng=LNG, l1="FD", l2="FD05")

    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_redis] = lambda: redis
    try:
        resp = await client.get(
            "/v1/map/nearby", params={"lat": LAT, "lng": LNG, "category": "shopping"}
        )
    finally:
        app.dependency_overrides.clear()

    ids = {i["contentId"] for i in resp.json()["data"]}
    assert ids == {"shop"}


@pytest.mark.asyncio
async def test_nearby_route_rejects_bad_category(db_session, client):
    # 의존성(get_db/get_redis)은 검증 실패와 무관하게 해석되므로 override 필요.
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_redis] = lambda: FakeRedis(decode_responses=False)
    try:
        resp = await client.get(
            "/v1/map/nearby", params={"lat": LAT, "lng": LNG, "category": "xxx"}
        )
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 422
