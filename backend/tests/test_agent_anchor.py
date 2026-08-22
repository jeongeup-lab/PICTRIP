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
from app.modules.agent.services import anchor as anchor_service
from app.modules.agent.services import phrasing as phrasing_service
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
    image: str = "http://kto/i.jpg",
) -> None:
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, addr1, "
            "first_image_url, show_flag, mapx, mapy, lcls_systm1, lcls_systm2, "
            "lcls_systm3) "
            "VALUES (:cid, :ctype, :t, '제주특별자치도 제주시 구좌읍 1', "
            ":img, 1, :lng, :lat, :l1, :l2, :l3)"
        ),
        {
            "cid": cid,
            "ctype": content_type,
            "t": title,
            "img": image,
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


def _vec(*values: float) -> str:
    padded = [*values, *([0.0] * (512 - len(values)))]
    return "[" + ",".join(str(value) for value in padded) + "]"


async def _embed(session: AsyncSession, cid: str, vec: str) -> None:
    await session.execute(
        text("INSERT INTO spot_embeddings (content_id, embedding) VALUES (:c, :v)"),
        {"c": cid, "v": vec},
    )


async def test_anchor_related_without_an_embedding_reports_no_results(
    db_session, client, anchor_seeded
) -> None:
    _override(db_session)
    try:
        res = await _ask_anchor(client, "a1", "related")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 422
    assert res.json()["error"]["code"] == "AGENT_NO_RESULTS"


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


async def test_anchor_rejects_an_unknown_action(db_session, client) -> None:
    _override(db_session)
    try:
        res = await _ask_anchor(client, "a1", "hotel")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 422
    assert res.json()["error"]["code"] == "VALIDATION_FAILED"


def test_anchor_card_carries_distance_tag_and_short_region() -> None:
    card = anchor_service.anchor_card(
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

    assert card.tag == "440m"
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

    response = anchor_service._anchor_crowd_response(row)

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

    assert anchor_service.anchor_card(row, has_crowd=True).hasCrowd is True
    assert anchor_service.anchor_card(row, has_crowd=False).hasCrowd is False


def test_the_travel_anchor_keeps_museums_that_the_map_predicate_drops() -> None:
    from app.modules.spots.categories import _predicate_sql
    from app.modules.spots.services.nearby import _predicate_for

    assert anchor_service.ANCHOR_CATEGORIES["nearby"] is NearbyCategory.attraction
    map_sql = _predicate_sql(_predicate_for(NearbyCategory.attraction, False))
    travel_sql = _predicate_sql(_predicate_for(NearbyCategory.attraction, True))

    assert "VE07" in map_sql
    assert "VE07" not in travel_sql


def test_an_anchor_with_nothing_nearby_is_an_answer_not_an_error() -> None:

    answer = anchor_service.empty_anchor_response("그리스신화박물관", "food", prior_steps=[])

    assert answer.spots == []
    assert answer.totalCount == 0
    assert "그리스신화박물관" in "".join(part.text for part in answer.answer)
    assert "맛집" in "".join(part.text for part in answer.answer)


def test_an_anchor_answer_leads_with_the_nearest_distance() -> None:
    segments = anchor_service.anchor_lead("성산일출봉", "food", nearest_m=420)

    text = "".join(s.text for s in segments)
    assert text.startswith("가장 가까운 맛집이 420m 거리예요.")
    assert [s.text for s in segments if s.emphasis] == ["420m"]


def test_a_sub_kilometre_distance_reads_in_metres_not_zero_point_something() -> None:
    assert phrasing_service.meters_label(38.0) == "40m"
    assert phrasing_service.meters_label(874.0) == "870m"
    assert phrasing_service.meters_label(4.0) == "10m"


def test_a_kilometre_scale_distance_keeps_the_kilometre_form() -> None:
    assert phrasing_service.meters_label(1000.0) == "1.0km"
    assert phrasing_service.meters_label(3210.0) == "3.2km"
    assert phrasing_service.meters_label(996.0) == "1.0km"


def test_a_close_anchor_never_leads_with_a_zero_distance() -> None:
    segments = anchor_service.anchor_lead("성산일출봉", "cafe", nearest_m=32.0)

    assert "".join(s.text for s in segments) == "가장 가까운 카페가 30m 거리예요."


def test_an_anchor_answer_without_a_distance_states_the_scope() -> None:
    segments = anchor_service.anchor_lead("성산일출봉", "cafe", nearest_m=None)

    assert "".join(s.text for s in segments) == "성산일출봉 주변 카페예요."


def test_an_anchor_answer_attaches_the_particle_each_noun_actually_takes() -> None:
    leads = {
        action: "".join(
            part.text for part in anchor_service.anchor_lead("성산일출봉", action, nearest_m=420)
        )
        for action in ("food", "cafe", "nearby")
    }

    assert leads["food"].startswith("가장 가까운 맛집이 ")
    assert leads["cafe"].startswith("가장 가까운 카페가 ")
    assert leads["nearby"].startswith("가장 가까운 볼거리가 ")


def test_an_empty_anchor_line_attaches_the_particle_each_noun_takes() -> None:
    lines = {
        action: "".join(
            part.text
            for part in anchor_service.empty_anchor_response(
                "성산일출봉", action, prior_steps=[]
            ).answer
        )
        for action in ("food", "cafe", "nearby")
    }

    assert "안에는 맛집이 없어요." in lines["food"]
    assert "안에는 카페가 없어요." in lines["cafe"]
    assert "안에는 볼거리가 없어요." in lines["nearby"]


def test_an_anchor_scope_line_ends_with_the_copula_each_noun_takes() -> None:
    scopes = {
        action: "".join(
            part.text for part in anchor_service.anchor_lead("성산일출봉", action, nearest_m=None)
        )
        for action in ("food", "cafe", "nearby")
    }

    assert scopes["food"] == "성산일출봉 주변 맛집이에요."
    assert scopes["cafe"] == "성산일출봉 주변 카페예요."
    assert scopes["nearby"] == "성산일출봉 주변 볼거리예요."
