from __future__ import annotations

import pytest
import pytest_asyncio
from fakeredis.aioredis import FakeRedis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.redis import get_redis
from app.kto.client import get_kto
from app.main import app
from app.modules.agent.repositories import CandidateRow
from app.modules.agent.services import ask as ask_service
from app.modules.spots.services import NearbyCategory, NearbySpotRow

ANCHOR_LAT, ANCHOR_LNG = 33.5567, 126.7597


def _override(db_session: AsyncSession) -> None:
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_redis] = lambda: FakeRedis(decode_responses=True)
    app.dependency_overrides[get_kto] = lambda: None


async def _spot(
    session: AsyncSession,
    cid: str,
    *,
    title: str,
    l1: str,
    l2: str | None,
    l3: str | None,
    content_type: int = 12,
    lat_offset: float = 0.0,
) -> None:
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, addr1, "
            "first_image_url, show_flag, mapx, mapy, lcls_systm1, lcls_systm2, "
            "lcls_systm3) "
            "VALUES (:cid, :ctype, :t, '제주특별자치도 제주시 구좌읍 1', "
            "'http://kto/i.jpg', 1, :lng, :lat, :l1, :l2, :l3)"
        ),
        {
            "cid": cid,
            "ctype": content_type,
            "t": title,
            "lng": ANCHOR_LNG,
            "lat": ANCHOR_LAT + lat_offset,
            "l1": l1,
            "l2": l2,
            "l3": l3,
        },
    )


async def _seed_anchor_world(session: AsyncSession) -> None:
    await _spot(session, "a1", title="김녕미로공원", l1="NA", l2="NA01", l3=None)
    await session.execute(
        text(
            "INSERT INTO spot_concentration "
            "(content_id, concentration_rate, base_ymd, raw_name) "
            "VALUES ('a1', 12.00, DATE '2026-07-01', 'n-a1')"
        )
    )
    await _spot(
        session,
        "f1",
        title="해녀촌식당",
        l1="FD",
        l2="FD01",
        l3=None,
        content_type=39,
        lat_offset=0.004,
    )
    await _spot(
        session,
        "f2",
        title="구좌횟집",
        l1="FD",
        l2="FD02",
        l3=None,
        content_type=39,
        lat_offset=0.009,
    )
    await _spot(
        session,
        "cf1",
        title="바닷가카페",
        l1="FD",
        l2="FD05",
        l3=None,
        content_type=39,
        lat_offset=0.006,
    )
    await _spot(session, "n1", title="비자림", l1="NA", l2="NA01", l3=None, lat_offset=0.008)
    await _spot(
        session,
        "far1",
        title="멀리있는식당",
        l1="FD",
        l2="FD01",
        l3=None,
        content_type=39,
        lat_offset=0.9,
    )
    await session.flush()


@pytest_asyncio.fixture
async def anchor_seeded(db_session: AsyncSession) -> None:
    await _seed_anchor_world(db_session)


async def _ask_anchor(client, content_id: str, action: str):  # type: ignore[no-untyped-def]
    return await client.post(
        "/v1/agent/ask",
        json={"anchor": {"contentId": content_id, "action": action}},
    )


@pytest.mark.integration
async def test_anchor_food_returns_nearby_restaurants_sorted_by_distance(
    db_session, client, anchor_seeded
) -> None:
    _override(db_session)
    try:
        res = await _ask_anchor(client, "a1", "food")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    data = res.json()["data"]
    assert [step["tool"] for step in data["steps"]] == ["nearby"]
    assert "김녕미로공원 주변 맛집" in data["steps"][0]["label"]
    assert [spot["contentId"] for spot in data["spots"]] == ["f1", "f2"]
    assert all(spot["tag"].endswith("km") for spot in data["spots"])
    assert data["refinements"] == []
    assert data["suggestions"] == []


@pytest.mark.integration
async def test_anchor_cafe_keeps_only_cafe_rows(db_session, client, anchor_seeded) -> None:
    _override(db_session)
    try:
        res = await _ask_anchor(client, "a1", "cafe")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    assert [spot["contentId"] for spot in res.json()["data"]["spots"]] == ["cf1"]


@pytest.mark.integration
async def test_anchor_nearby_excludes_the_anchor_itself(db_session, client, anchor_seeded) -> None:
    _override(db_session)
    try:
        res = await _ask_anchor(client, "a1", "nearby")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    spots = res.json()["data"]["spots"]
    assert [spot["contentId"] for spot in spots] == ["n1"]


@pytest.mark.integration
async def test_anchor_crowd_answers_without_spots(db_session, client, anchor_seeded) -> None:
    _override(db_session)
    try:
        res = await _ask_anchor(client, "a1", "crowd")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    data = res.json()["data"]
    assert [step["tool"] for step in data["steps"]] == ["concentration"]
    assert data["spots"] == []
    assert data["totalCount"] == 0
    joined = "".join(part["text"] for part in data["answer"])
    assert "한산" in joined
    assert "하위 " not in joined


@pytest.mark.integration
async def test_anchor_crowd_reports_missing_concentration(
    db_session, client, anchor_seeded
) -> None:
    _override(db_session)
    try:
        res = await _ask_anchor(client, "n1", "crowd")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    joined = "".join(part["text"] for part in res.json()["data"]["answer"])
    assert "혼잡도 정보가 아직 없어요" in joined


@pytest.mark.integration
async def test_anchor_with_unknown_spot_reports_no_results(
    db_session, client, anchor_seeded
) -> None:
    _override(db_session)
    try:
        res = await _ask_anchor(client, "ghost", "food")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 422
    assert res.json()["error"]["code"] == "AGENT_NO_RESULTS"


@pytest.mark.integration
async def test_anchor_rejects_a_photo_alongside(db_session, client, anchor_seeded) -> None:
    _override(db_session)
    try:
        res = await client.post(
            "/v1/agent/ask",
            files={"photo": ("p.jpg", b"\xff\xd8\xff", "image/jpeg")},
            data={"anchor": '{"contentId": "a1", "action": "food"}'},
        )
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 422
    assert res.json()["error"]["code"] == "VALIDATION_FAILED"


@pytest.mark.integration
async def test_anchor_rejects_an_unknown_action(db_session, client) -> None:
    _override(db_session)
    try:
        res = await _ask_anchor(client, "a1", "hotel")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 422
    assert res.json()["error"]["code"] == "VALIDATION_FAILED"


def test_anchor_card_carries_distance_tag_and_short_region() -> None:
    card = ask_service._anchor_card(
        NearbySpotRow(
            content_id="f1",
            title="해녀촌식당",
            first_image_url="http://kto/i.jpg",
            addr1="제주특별자치도 제주시 구좌읍 1",
            mapx=ANCHOR_LNG,
            mapy=ANCHOR_LAT,
            dist=442.0,
            cpyrht_div_cd="Type1",
        ),
        has_crowd=False,
    )

    assert card.tag == "0.4km"
    assert card.regionLabel == "제주특별자치도 제주시"


def test_anchor_crowd_response_emphasises_percentile_for_calm_spots() -> None:
    row = CandidateRow(
        content_id="a1",
        title="김녕미로공원",
        addr1=None,
        region_name=None,
        sigungu_name=None,
        lat=ANCHOR_LAT,
        lng=ANCHOR_LNG,
        image_url=None,
        cpyrht_div_cd=None,
        concentration_rate=12.0,
        percentile=12,
    )

    response = ask_service._anchor_crowd_response(row)

    joined = "".join(part.text for part in response.answer)
    assert "한산" in joined
    assert "하위 12%" in joined
    assert response.spots == []


def test_anchor_card_reports_whether_crowd_data_exists() -> None:
    row = NearbySpotRow(
        content_id="f1",
        title="해녀촌식당",
        first_image_url="http://kto/i.jpg",
        addr1="제주특별자치도 제주시 구좌읍 1",
        mapx=ANCHOR_LNG,
        mapy=ANCHOR_LAT,
        dist=442.0,
        cpyrht_div_cd="Type1",
    )

    assert ask_service._anchor_card(row, has_crowd=True).hasCrowd is True
    assert ask_service._anchor_card(row, has_crowd=False).hasCrowd is False


def test_the_travel_anchor_keeps_museums_that_the_map_predicate_drops() -> None:
    from app.modules.spots.services.nearby import _predicate_for, _predicate_sql

    assert ask_service.ANCHOR_CATEGORIES["nearby"] is NearbyCategory.attraction
    map_sql = _predicate_sql(_predicate_for(NearbyCategory.attraction, False))
    travel_sql = _predicate_sql(_predicate_for(NearbyCategory.attraction, True))

    assert "VE07" in map_sql
    assert "VE07" not in travel_sql


@pytest.mark.integration
async def test_an_anchor_without_a_content_id_centres_on_my_coords(
    db_session, client, anchor_seeded
) -> None:
    _override(db_session)
    try:
        res = await client.post(
            "/v1/agent/ask",
            json={"anchor": {"action": "food"}, "lat": ANCHOR_LAT, "lng": ANCHOR_LNG},
        )
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    data = res.json()["data"]
    assert data["spots"]
    assert "내 위치 주변 맛집" in "".join(part["text"] for part in data["answer"])
    assert data["steps"][0]["label"].startswith("내 위치 주변 맛집")


@pytest.mark.integration
async def test_an_anchor_with_neither_a_spot_nor_coords_is_rejected(
    db_session, client, anchor_seeded
) -> None:
    _override(db_session)
    try:
        res = await client.post("/v1/agent/ask", json={"anchor": {"action": "food"}})
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 422
    assert res.json()["error"]["code"] == "VALIDATION_FAILED"


@pytest.mark.integration
async def test_asking_my_own_coords_whether_they_are_busy_is_rejected(
    db_session, client, anchor_seeded
) -> None:
    _override(db_session)
    try:
        res = await client.post(
            "/v1/agent/ask",
            json={"anchor": {"action": "crowd"}, "lat": ANCHOR_LAT, "lng": ANCHOR_LNG},
        )
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 422
    assert res.json()["error"]["code"] == "VALIDATION_FAILED"
