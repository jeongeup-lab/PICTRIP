from __future__ import annotations

import pytest_asyncio
from fakeredis.aioredis import FakeRedis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.redis import get_redis
from app.kto.client import get_kto
from app.main import app

LAT, LNG = 35.15, 129.05


def _override(db_session: AsyncSession) -> None:
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_redis] = lambda: FakeRedis(decode_responses=True)
    app.dependency_overrides[get_kto] = lambda: None


async def _seed_region(session: AsyncSession) -> None:
    await session.execute(
        text(
            "INSERT INTO regions (ldong_regn_cd, ldong_regn_nm) VALUES (:c, :n) "
            "ON CONFLICT DO NOTHING"
        ),
        {"c": "26", "n": "부산광역시"},
    )
    await session.execute(
        text(
            "INSERT INTO sigungus (ldong_signgu_cd, ldong_regn_cd, ldong_signgu_nm) "
            "VALUES (:c, :r, :n) ON CONFLICT DO NOTHING"
        ),
        {"c": "26380", "r": "26", "n": "사하구"},
    )


async def _seed_nearby(
    session: AsyncSession,
    cid: str,
    *,
    lat: float,
    lng: float,
    img: str | None = "http://kto/i.jpg",
) -> None:
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, first_image_url, "
            "show_flag, mapx, mapy, lcls_systm1, ldong_regn_cd, ldong_signgu_cd) "
            "VALUES (:cid, 12, :t, :img, 1, :lng, :lat, 'NA', '26', '26380')"
        ),
        {"cid": cid, "t": f"t-{cid}", "img": img, "lng": lng, "lat": lat},
    )


async def _seed_concentration(
    session: AsyncSession,
    cid: str,
    *,
    rate: str,
    overview: str | None,
) -> None:
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, first_image_url, "
            "show_flag, ldong_regn_cd, ldong_signgu_cd, lcls_systm1) "
            "VALUES (:cid, 12, :t, 'http://kto/i.jpg', 1, '26', '26380', 'NA')"
        ),
        {"cid": cid, "t": f"t-{cid}"},
    )
    await session.execute(
        text(
            "INSERT INTO spot_concentration "
            "(content_id, concentration_rate, base_ymd, raw_name) "
            "VALUES (:cid, :rate, DATE '2026-07-01', :rn)"
        ),
        {"cid": cid, "rate": rate, "rn": f"n-{cid}"},
    )
    if overview is not None:
        await session.execute(
            text(
                "INSERT INTO spot_details (content_id, content_type_id, overview) "
                "VALUES (:cid, 12, :ov)"
            ),
            {"cid": cid, "ov": overview},
        )


@pytest_asyncio.fixture
async def seeded_nearby(db_session: AsyncSession) -> None:
    await _seed_region(db_session)
    await _seed_nearby(db_session, "n1", lat=LAT + 0.001, lng=LNG)
    await _seed_nearby(db_session, "n2", lat=LAT + 0.003, lng=LNG)
    await db_session.flush()


@pytest_asyncio.fixture
async def seeded_concentration(db_session: AsyncSession) -> None:
    await _seed_region(db_session)
    await _seed_concentration(db_session, "c90", rate="90.00", overview="설명 90")
    await _seed_concentration(db_session, "c60", rate="60.00", overview="설명 60")
    await _seed_concentration(db_session, "c10", rate="10.00", overview="설명 10")
    await db_session.flush()


async def test_around_requires_coords(db_session, client) -> None:
    _override(db_session)
    try:
        res = await client.get("/v1/home/channels/around")
    finally:
        app.dependency_overrides.clear()
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "VALIDATION_FAILED"


async def test_around_returns_nearby_cards_with_dist(db_session, client, seeded_nearby) -> None:
    _override(db_session)
    try:
        res = await client.get("/v1/home/channels/around", params={"lat": LAT, "lng": LNG})
    finally:
        app.dependency_overrides.clear()
    assert res.status_code == 200
    body = res.json()["data"]
    cards = body["cards"]
    assert 1 <= len(cards) <= 10
    assert cards[0]["dist"] is not None
    assert cards[0]["saveable"] is True
    assert cards[0]["regionLabel"] == "부산광역시 사하구"
    assert body["label"] == "Around"
    assert body["key"] == "around"


async def test_hot_returns_ranked_cards(db_session, client, seeded_concentration) -> None:
    _override(db_session)
    try:
        res = await client.get("/v1/home/channels/hot")
    finally:
        app.dependency_overrides.clear()
    assert res.status_code == 200
    cards = res.json()["data"]["cards"]
    assert cards[0]["rank"] == 1
    assert cards[0]["dday"] is None
    assert cards[0]["regionLabel"] == "부산광역시 사하구"


async def test_hidden_returns_cards_ranked_from_the_quietest(
    db_session, client, seeded_concentration
) -> None:
    _override(db_session)
    try:
        res = await client.get("/v1/home/channels/hidden")
    finally:
        app.dependency_overrides.clear()
    assert res.status_code == 200
    cards = res.json()["data"]["cards"]
    assert len(cards) >= 1
    assert [c["rank"] for c in cards] == list(range(1, len(cards) + 1))
    assert all(c["tag"] is None for c in cards)


async def test_kto_channel_returns_kto_cards(db_session, client) -> None:
    from unittest.mock import AsyncMock

    festa_items = [
        {
            "contentid": "F1",
            "title": "무주 반딧불 축제",
            "addr1": "전북 무주군 무주읍",
            "firstimage": "http://tong.visitkorea.or.kr/f1.jpg",
            "eventstartdate": "20260101",
            "eventenddate": "20991231",
        }
    ]
    kto = AsyncMock()
    kto.call = AsyncMock(return_value=festa_items)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_redis] = lambda: FakeRedis(decode_responses=True)
    app.dependency_overrides[get_kto] = lambda: kto
    try:
        res = await client.get("/v1/home/channels/festa")
    finally:
        app.dependency_overrides.clear()
    assert res.status_code == 200
    body = res.json()["data"]
    assert body["label"] == "Festa"
    assert len(body["cards"]) == 1
    assert body["cards"][0]["contentId"] == "F1"


async def test_unknown_channel_404(db_session, client) -> None:
    _override(db_session)
    try:
        res = await client.get("/v1/home/channels/nope")
    finally:
        app.dependency_overrides.clear()
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
