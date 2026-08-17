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
async def seeded_concentration(db_session: AsyncSession) -> None:
    await _seed_region(db_session)
    await _seed_concentration(db_session, "c90", rate="90.00", overview="설명 90")
    await _seed_concentration(db_session, "c60", rate="60.00", overview="설명 60")
    await _seed_concentration(db_session, "c10", rate="10.00", overview="설명 10")
    await db_session.flush()


async def test_around_and_hot_moved_out_of_the_channel_rail(db_session, client) -> None:
    _override(db_session)
    try:
        around = await client.get("/v1/home/channels/around", params={"lat": LAT, "lng": LNG})
        hot = await client.get("/v1/home/channels/hot")
    finally:
        app.dependency_overrides.clear()
    assert around.status_code == 404
    assert hot.status_code == 404


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


def _festa_item(cid: str) -> dict[str, str]:
    return {
        "contentid": cid,
        "title": f"축제-{cid}",
        "addr1": "전북 무주군 무주읍",
        "firstimage": "http://tong.visitkorea.or.kr/f1.jpg",
        "eventstartdate": "20260101",
        "eventenddate": "20991231",
    }


async def _get_festa_cards(db_session, client, items: list[dict[str, str]]):
    from unittest.mock import AsyncMock

    kto = AsyncMock()
    kto.call = AsyncMock(return_value=items)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_redis] = lambda: FakeRedis(decode_responses=True)
    app.dependency_overrides[get_kto] = lambda: kto
    try:
        res = await client.get("/v1/home/channels/festa")
    finally:
        app.dependency_overrides.clear()
    assert res.status_code == 200
    return res.json()["data"]


async def test_kto_channel_returns_kto_cards(db_session, client) -> None:
    await db_session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, first_image_url, "
            "show_flag, lcls_systm1) VALUES ('F1', 15, '축제-F1', 'http://kto/f1.jpg', 1, 'EV')"
        )
    )
    body = await _get_festa_cards(db_session, client, [_festa_item("F1")])
    assert body["label"] == "Festa"
    assert len(body["cards"]) == 1
    assert body["cards"][0]["contentId"] == "F1"
    assert body["cards"][0]["saveable"] is True


async def test_kto_channel_keeps_card_but_drops_unresolvable_detail(db_session, client) -> None:
    await db_session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, first_image_url, "
            "show_flag, lcls_systm1) VALUES ('F2', 15, '축제-F2', 'http://kto/f2.jpg', 0, 'EV')"
        )
    )
    body = await _get_festa_cards(db_session, client, [_festa_item("F2"), _festa_item("F3")])
    assert len(body["cards"]) == 2
    for card in body["cards"]:
        assert card["contentId"] is None
        assert card["saveable"] is False


async def test_unknown_channel_404(db_session, client) -> None:
    _override(db_session)
    try:
        res = await client.get("/v1/home/channels/nope")
    finally:
        app.dependency_overrides.clear()
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
