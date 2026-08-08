from __future__ import annotations

import json
import tempfile
from collections.abc import Awaitable, Callable
from datetime import date, timedelta
from typing import get_args

import pytest
import pytest_asyncio
from fakeredis.aioredis import FakeRedis
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import formparsers

from app.core.db import get_db
from app.core.redis import get_redis
from app.kto.client import get_kto
from app.main import app
from app.modules.agent import llm, repositories
from app.modules.agent.errors import AgentIntentUnavailable, AgentNoResults
from app.modules.agent.repositories import CandidateRow, VectorMatchRow
from app.modules.agent.routes import MAX_BODY_BYTES
from app.modules.agent.schemas import (
    MAX_HINT_TOKENS,
    MAX_KEYWORDS,
    MAX_NAMED_PLACES,
    MAX_REGION_HINTS,
    MAX_TEXT_CHARS,
    AgentSpotCard,
    AskResponse,
    ExtractedPlace,
    Mood,
    QueryIntent,
    RefinePatch,
)
from app.modules.agent.services import ask as ask_service
from app.modules.agent.services import intent as intent_service
from app.modules.agent.services import photo as photo_service
from app.modules.agent.services import refine as refine_service
from app.modules.agent.services import resolve as resolve_service
from app.modules.agent.services import retrieve
from app.modules.agent.services import suggest as suggest_service
from app.modules.feed.services import kto_channels
from app.modules.feed.services.channels import ChannelCardRow
from app.modules.spots.services import (
    MAX_REGION_TOKENS,
    map_region_tokens_to_prefixes,
    map_region_tokens_to_sido,
)
from app.web.errors import KtoApiUnavailable

LAT, LNG = 35.15, 129.05
_VEC = "[" + ",".join(["0.1"] * 512) + "]"


def _row(
    cid: str,
    *,
    rate: float | None,
    lat: float = LAT,
    lng: float = LNG,
    percentile: int | None = None,
) -> CandidateRow:
    return CandidateRow(
        content_id=cid,
        title=f"t-{cid}",
        addr1="부산광역시 사하구 1",
        region_name="부산광역시",
        sigungu_name="사하구",
        lat=lat,
        lng=lng,
        image_url="http://kto/i.jpg",
        cpyrht_div_cd="Type1",
        concentration_rate=rate,
        percentile=percentile,
    )


def _pool() -> list[CandidateRow]:
    return [_row(f"c{i}", rate=float(i * 10), percentile=(i + 1) * 10) for i in range(10)]


def test_quiet_preference_keeps_the_lowest_percentiles() -> None:
    kept = retrieve.filter_by_crowd(_pool(), "quiet")

    assert [row.content_id for row in kept] == ["c0", "c1", "c2"]


def test_popular_preference_keeps_the_highest_percentiles() -> None:
    kept = retrieve.filter_by_crowd(_pool(), "popular")

    assert [row.content_id for row in kept] == ["c6", "c7", "c8", "c9"]


def test_crowd_filter_falls_back_when_no_row_carries_a_percentile() -> None:
    rows = [_row("a", rate=None), _row("b", rate=None)]

    assert retrieve.filter_by_crowd(rows, "quiet") == rows


def test_candidate_order_follows_intent() -> None:
    assert retrieve.candidate_order(preference="quiet", near=False) == "rate_asc"
    assert retrieve.candidate_order(preference="popular", near=False) == "rate_desc"
    assert retrieve.candidate_order(preference="any", near=False) == "id"
    assert retrieve.candidate_order(preference="quiet", near=True) == "distance"


def test_crowd_label_buckets_by_rate() -> None:
    assert retrieve.crowd_label(_row("a", rate=90.0)) == "붐빔"
    assert retrieve.crowd_label(_row("b", rate=50.0)) == "보통"
    assert retrieve.crowd_label(_row("c", rate=10.0)) == "한산"
    assert retrieve.crowd_label(_row("d", rate=None)) is None


def test_card_tag_prefers_distance_then_percentile() -> None:
    pool = _pool()
    quiet = QueryIntent(crowdPreference="quiet")

    near_card = ask_service._card(pool[0], intent=quiet, lat=LAT, lng=LNG, near=True)
    quiet_card = ask_service._card(pool[0], intent=quiet, lat=None, lng=None, near=False)

    assert near_card.tag == "10m"
    assert ask_service._is_distance_tag(near_card.tag)
    assert quiet_card.tag == "하위 10%"


def test_a_quiet_answer_leads_with_the_percentile_not_the_count() -> None:
    segments = ask_service._answer(
        _pool()[:4],
        intent=QueryIntent(crowdPreference="quiet"),
        near=False,
        lat=None,
        lng=None,
    )

    text = "".join(s.text for s in segments)
    assert text.startswith("혼잡도 ")
    assert "안쪽으로만 골랐어요." in text
    assert "4곳" in text
    assert next(s.text for s in segments if s.emphasis).startswith("하위 ")


def test_a_near_answer_leads_with_the_closest_distance() -> None:
    segments = ask_service._answer(
        _pool()[:4],
        intent=QueryIntent(nearMe=True),
        near=True,
        lat=35.0,
        lng=128.0,
    )

    text = "".join(s.text for s in segments)
    assert text.startswith("가장 가까운 곳이 ")
    assert ask_service._is_distance_tag(next(s.text for s in segments if s.emphasis))


def _photo_spots(rows: list[CandidateRow], *, near: bool) -> list[AgentSpotCard]:
    similarity = {row.content_id: 0.9 for row in rows}
    return [
        ask_service._photo_card(
            row,
            similarity=similarity,
            lat=LAT if near else None,
            lng=LNG if near else None,
            near=near,
        )
        for row in rows
    ]


def test_a_similarity_ordered_photo_answer_leads_with_the_first_card() -> None:
    rows = _pool()[:3]

    segments = ask_service._photo_answer(
        rows,
        _photo_spots(rows, near=False),
        near=False,
        lat=None,
        lng=None,
        widened=None,
    )

    text = "".join(s.text for s in segments)
    assert text.startswith("t-c0이 가장 비슷해요.")
    assert "사진과 닮은 곳으로 3곳이에요." in text
    assert next(s.text for s in segments if s.emphasis) == "t-c0"


def test_a_distance_ordered_photo_answer_leads_with_the_distance_not_similarity() -> None:
    rows = [
        _row("near", rate=None, lat=35.1501, lng=129.05),
        _row("far", rate=None, lat=35.20, lng=129.05),
    ]

    segments = ask_service._photo_answer(
        rows,
        _photo_spots(rows, near=True),
        near=True,
        lat=LAT,
        lng=LNG,
        widened=None,
    )

    text = "".join(s.text for s in segments)
    assert text.startswith("가장 가까운 곳이 ")
    assert "가장 비슷해요" not in text
    assert "사진과 닮은 곳으로 2곳이에요." in text
    assert ask_service._is_distance_tag(next(s.text for s in segments if s.emphasis))


def test_a_photo_answer_never_emphasises_a_bare_count() -> None:
    rows = _pool()[:2]

    for near in (False, True):
        segments = ask_service._photo_answer(
            rows,
            _photo_spots(rows, near=near),
            near=near,
            lat=LAT if near else None,
            lng=LNG if near else None,
            widened=None,
        )

        assert all("곳이에요" not in s.text for s in segments if s.emphasis)


def test_an_answer_with_no_specific_fact_leads_with_the_conditions() -> None:
    segments = ask_service._answer(
        _pool()[:4],
        intent=QueryIntent(regionHints=["통영"], categoryKeywords=["계곡"]),
        near=False,
        lat=None,
        lng=None,
    )

    text = "".join(s.text for s in segments)
    assert text.startswith("통영 + 계곡 조건으로 4곳이에요.")


def test_an_answer_with_nothing_nameable_keeps_the_plain_opening() -> None:
    segments = ask_service._answer(
        _pool()[:4],
        intent=QueryIntent(namedPlaces=[ExtractedPlace(name="감천문화마을")]),
        near=False,
        lat=None,
        lng=None,
    )

    assert "".join(s.text for s in segments).startswith("조건에 맞는 곳으로 4곳이에요.")


def test_a_widened_answer_leads_with_the_region_it_widened_to() -> None:
    segments = ask_service._answer(
        _pool()[:4],
        intent=QueryIntent(regionHints=["수영"]),
        near=False,
        lat=None,
        lng=None,
        region_widened=retrieve.RegionScope(
            prefixes=["부산광역시"],
            sido_prefixes=["부산광역시"],
            narrowed_hints=("수영구",),
            narrowed_sidos=("부산광역시",),
        ),
    )

    text = "".join(s.text for s in segments)
    assert text.startswith("수영구 안에서는 찾지 못해 부산광역시 전체에서 골랐어요.")
    assert "4곳" in text


def test_an_answer_never_emphasises_a_bare_count() -> None:
    segments = ask_service._answer(
        _pool()[:4],
        intent=QueryIntent(crowdPreference="quiet"),
        near=False,
        lat=None,
        lng=None,
    )

    assert "4곳" not in [s.text for s in segments if s.emphasis]


def _override(db_session: AsyncSession) -> None:
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_redis] = lambda: FakeRedis(decode_responses=True)
    app.dependency_overrides[get_kto] = lambda: None


async def _seed(session: AsyncSession) -> None:
    await session.execute(
        text(
            "INSERT INTO regions (ldong_regn_cd, ldong_regn_nm) VALUES ('26', '부산광역시') "
            "ON CONFLICT DO NOTHING"
        )
    )
    await session.execute(
        text(
            "INSERT INTO sigungus (ldong_signgu_cd, ldong_regn_cd, ldong_signgu_nm) "
            "VALUES ('26380', '26', '사하구') ON CONFLICT DO NOTHING"
        )
    )
    await session.execute(
        text(
            "INSERT INTO sigungus (ldong_signgu_cd, ldong_regn_cd, ldong_signgu_nm) "
            "VALUES ('26350', '26', '해운대구'), ('26500', '26', '수영구') ON CONFLICT DO NOTHING"
        )
    )
    await session.execute(
        text(
            "INSERT INTO lcls_systm_codes "
            "(lcls_systm3_cd, lcls_systm2_cd, lcls_systm1_cd, lcls_systm3_nm, "
            "lcls_systm2_nm, lcls_systm1_nm) "
            "VALUES ('NA010100', 'NA01', 'NA', '계곡', '자연관광지', '자연') "
            "ON CONFLICT DO NOTHING"
        )
    )
    await session.execute(
        text(
            "INSERT INTO regions (ldong_regn_cd, ldong_regn_nm) "
            "VALUES ('50', '제주특별자치도') ON CONFLICT DO NOTHING"
        )
    )
    for cid, rate, offset in (("v1", "12.00", 0.03), ("v2", "48.00", 0.02), ("v3", "88.00", 0.01)):
        await session.execute(
            text(
                "INSERT INTO spots (content_id, content_type_id, title, addr1, "
                "first_image_url, show_flag, mapx, mapy, lcls_systm1, lcls_systm3, "
                "ldong_regn_cd, ldong_signgu_cd) "
                "VALUES (:cid, 12, :t, '부산광역시 사하구 1', 'http://kto/i.jpg', 1, "
                ":lng, :lat, 'NA', 'NA010100', '26', '26380')"
            ),
            {"cid": cid, "t": f"계곡-{cid}", "lng": LNG, "lat": LAT + offset},
        )
        await session.execute(
            text(
                "INSERT INTO spot_concentration "
                "(content_id, concentration_rate, base_ymd, raw_name) "
                "VALUES (:cid, :rate, DATE '2026-07-01', :rn)"
            ),
            {"cid": cid, "rate": rate, "rn": f"n-{cid}"},
        )
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, addr1, "
            "first_image_url, show_flag, mapx, mapy, lcls_systm1, lcls_systm3, "
            "ldong_regn_cd) "
            "VALUES ('j1', 12, '제주계곡', '제주특별자치도 서귀포시 1', "
            "'http://kto/i.jpg', 1, 126.5, 33.4, 'NA', 'NA010100', '50')"
        )
    )
    await session.execute(
        text(
            "INSERT INTO spot_concentration "
            "(content_id, concentration_rate, base_ymd, raw_name) "
            "VALUES ('j1', 30.00, DATE '2026-07-01', 'n-j1')"
        )
    )
    await session.execute(
        text(
            "INSERT INTO lcls_systm_codes "
            "(lcls_systm3_cd, lcls_systm2_cd, lcls_systm1_cd, lcls_systm3_nm, "
            "lcls_systm2_nm, lcls_systm1_nm) "
            "VALUES ('VE070100', 'VE07', 'VE', '박물관', '전시시설', '문화관광') "
            "ON CONFLICT DO NOTHING"
        )
    )
    await session.execute(
        text(
            "INSERT INTO lcls_systm_codes "
            "(lcls_systm3_cd, lcls_systm2_cd, lcls_systm1_cd, lcls_systm3_nm, "
            "lcls_systm2_nm, lcls_systm1_nm) "
            "VALUES ('EX070100', 'EX07', 'EX', '기타체험관광', '기타체험', '체험관광') "
            "ON CONFLICT DO NOTHING"
        )
    )
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, addr1, "
            "first_image_url, show_flag, mapx, mapy, lcls_systm1, lcls_systm2, "
            "lcls_systm3, ldong_regn_cd, ldong_signgu_cd) "
            "VALUES ('m1', 14, '부산박물관', '부산광역시 사하구 2', "
            "'http://kto/i.jpg', 1, :lng, :lat, 'VE', 'VE07', 'VE070100', '26', '26380')"
        ),
        {"lng": LNG, "lat": LAT},
    )
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, addr1, "
            "first_image_url, show_flag, mapx, mapy, lcls_systm1, lcls_systm2, "
            "lcls_systm3, ldong_regn_cd, ldong_signgu_cd) "
            "VALUES ('e1', 12, '갯벌체험마을', '부산광역시 사하구 3', "
            "'http://kto/i.jpg', 1, :lng, :lat, 'EX', 'EX07', 'EX070100', '26', '26380')"
        ),
        {"lng": LNG, "lat": LAT},
    )
    await session.execute(
        text(
            "INSERT INTO spot_moods (content_id, mood_id, confidence, source) "
            "SELECT 'v1', id, 1.0, 'code' FROM moods WHERE code = 'night' "
            "ON CONFLICT DO NOTHING"
        )
    )
    await session.flush()


@pytest_asyncio.fixture
async def seeded(db_session: AsyncSession) -> None:
    await _seed(db_session)


@pytest.mark.integration
async def test_ask_runs_the_pipeline_and_reports_real_steps(
    db_session, client, seeded, monkeypatch
) -> None:
    async def fake_intent(question: str) -> QueryIntent:
        return QueryIntent(categoryKeywords=["계곡"], regionHints=["부산"], crowdPreference="quiet")

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    _override(db_session)
    try:
        res = await client.post(
            "/v1/agent/ask",
            json={"question": "여름에 시원하고 사람 적은 부산 계곡"},
        )
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    data = res.json()["data"]
    assert [step["tool"] for step in data["steps"]] == [
        "intent",
        "category_search",
        "concentration",
    ]
    assert data["steps"][1]["badge"] == "3곳"
    assert data["spots"]
    assert data["spots"][0]["tag"].startswith("하위 ")
    assert data["spots"][0]["regionLabel"] == "부산광역시 사하구"
    assert data["totalCount"] >= 1


@pytest.mark.integration
async def test_ask_rejects_a_request_without_question_or_photo(db_session, client) -> None:
    _override(db_session)
    try:
        res = await client.post("/v1/agent/ask", json={})
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 422
    assert res.json()["error"]["code"] == "VALIDATION_FAILED"


@pytest.mark.integration
async def test_nothing_matching_answers_with_zero_and_a_way_out(
    db_session, client, seeded, monkeypatch
) -> None:
    async def fake_intent(question: str) -> QueryIntent:
        return QueryIntent(categoryKeywords=["박물관"], regionHints=["제주"])

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    _override(db_session)
    try:
        res = await client.post("/v1/agent/ask", json={"question": "제주 박물관"})
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    data = res.json()["data"]
    assert data["spots"] == []
    assert data["totalCount"] == 0
    answer = "".join(segment["text"] for segment in data["answer"])
    assert "없어요" in answer
    assert [chip["label"] for chip in data["refinements"]] == ["지역 넓히기"]


@pytest.mark.integration
async def test_a_zero_turn_keeps_the_funnel_steps_that_show_where_it_died(
    db_session, client, seeded, monkeypatch
) -> None:
    async def fake_intent(question: str) -> QueryIntent:
        return QueryIntent(categoryKeywords=["박물관"], regionHints=["제주"])

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    _override(db_session)
    try:
        res = await client.post("/v1/agent/ask", json={"question": "제주 박물관"})
    finally:
        app.dependency_overrides.clear()

    steps = res.json()["data"]["steps"]
    assert [step["badge"] for step in steps if step["tool"] == "category_search"] == ["0곳"]


@pytest.mark.integration
async def test_a_zero_turn_offers_only_conditions_that_are_still_applied(
    db_session, client, seeded, monkeypatch
) -> None:
    async def fake_intent(question: str) -> QueryIntent:
        return QueryIntent(categoryKeywords=["박물관"], regionHints=["제주"], indoorOnly=True)

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    _override(db_session)
    try:
        res = await client.post("/v1/agent/ask", json={"question": "제주 실내 박물관"})
    finally:
        app.dependency_overrides.clear()

    data = res.json()["data"]
    assert data["intent"]["indoorOnly"] is True
    assert data["intent"]["categoryKeywords"] == []
    labels = [chip["label"] for chip in data["refinements"]]
    assert labels == ["지역 넓히기"]
    assert not any("박물관" in label for label in labels)


@pytest.mark.integration
async def test_a_sigungu_hint_does_not_leak_the_rest_of_the_sido(
    db_session, client, seeded, monkeypatch
) -> None:
    async def fake_intent(question: str) -> QueryIntent:
        return QueryIntent(categoryKeywords=["계곡"], regionHints=["사하"])

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    _override(db_session)
    try:
        res = await client.post("/v1/agent/ask", json={"question": "사하 계곡"})
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    data = res.json()["data"]
    assert {spot["contentId"] for spot in data["spots"]} == {"v1", "v2", "v3"}
    assert not any("넓힘" in step["label"] for step in data["steps"])


@pytest.mark.integration
async def test_an_empty_sigungu_widens_to_the_sido_and_says_so(
    db_session, client, seeded, monkeypatch
) -> None:
    async def fake_intent(question: str) -> QueryIntent:
        return QueryIntent(categoryKeywords=["계곡"], regionHints=["수영"])

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    _override(db_session)
    try:
        res = await client.post("/v1/agent/ask", json={"question": "수영 계곡"})
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    data = res.json()["data"]
    assert {spot["contentId"] for spot in data["spots"]} == {"v1", "v2", "v3"}
    answer = "".join(segment["text"] for segment in data["answer"])
    assert "수영" in answer
    assert "부산광역시" in answer
    assert any("넓힘" in step["label"] for step in data["steps"])


@pytest.mark.integration
async def test_question_region_hint_narrows_the_search(
    db_session, client, seeded, monkeypatch
) -> None:
    async def fake_intent(question: str) -> QueryIntent:
        return QueryIntent(categoryKeywords=["계곡"], regionHints=["제주"])

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    _override(db_session)
    try:
        res = await client.post("/v1/agent/ask", json={"question": "제주 계곡"})
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    data = res.json()["data"]
    assert [spot["contentId"] for spot in data["spots"]] == ["j1"]
    assert data["totalCount"] == 1


async def _seed_wide(session: AsyncSession) -> None:
    for i in range(5):
        cid = f"w{i}"
        await session.execute(
            text(
                "INSERT INTO spots (content_id, content_type_id, title, addr1, "
                "first_image_url, show_flag, mapx, mapy, lcls_systm1, lcls_systm3, "
                "ldong_regn_cd, ldong_signgu_cd) "
                "VALUES (:cid, 12, :t, '부산광역시 사하구 1', 'http://kto/i.jpg', 1, "
                ":lng, :lat, 'NA', 'NA010100', '26', '26380')"
            ),
            {"cid": cid, "t": f"계곡-{cid}", "lng": LNG, "lat": LAT + 0.1 + i * 0.01},
        )
    await session.flush()


@pytest_asyncio.fixture
async def seeded_wide(db_session: AsyncSession) -> None:
    await _seed(db_session)
    await _seed_wide(db_session)


@pytest.mark.integration
async def test_total_count_matches_the_spot_list_the_user_can_open(
    db_session, client, seeded_wide, monkeypatch
) -> None:
    async def fake_intent(question: str) -> QueryIntent:
        return QueryIntent(categoryKeywords=["계곡"], regionHints=["부산"])

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    _override(db_session)
    try:
        res = await client.post("/v1/agent/ask", json={"question": "부산 계곡"})
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    data = res.json()["data"]
    assert len(data["spots"]) == 8
    assert data["totalCount"] == len(data["spots"])


@pytest.mark.integration
async def test_result_list_is_capped_and_total_count_follows_the_cap(
    db_session, client, seeded_wide, monkeypatch
) -> None:
    async def fake_intent(question: str) -> QueryIntent:
        return QueryIntent(categoryKeywords=["계곡"])

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    monkeypatch.setattr(retrieve, "RESULT_LIMIT", 3)
    _override(db_session)
    try:
        res = await client.post("/v1/agent/ask", json={"question": "부산 계곡"})
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    data = res.json()["data"]
    assert len(data["spots"]) == 3
    assert data["totalCount"] == 3


@pytest.mark.integration
async def test_near_me_orders_candidates_by_distance_in_sql(
    db_session, client, seeded, monkeypatch
) -> None:
    async def fake_intent(question: str) -> QueryIntent:
        return QueryIntent(categoryKeywords=["계곡"], regionHints=["부산"], nearMe=True)

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    _override(db_session)
    try:
        res = await client.post(
            "/v1/agent/ask",
            json={"question": "부산 근처 계곡", "lat": LAT, "lng": LNG},
        )
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    data = res.json()["data"]
    assert [spot["contentId"] for spot in data["spots"]] == ["v3", "v2", "v1"]
    assert [step["tool"] for step in data["steps"]][-1] == "nearby"
    assert all(ask_service._is_distance_tag(spot["tag"]) for spot in data["spots"])


@pytest.mark.integration
async def test_quiet_percentile_comes_from_sql_not_the_truncated_pool(
    db_session, client, seeded, monkeypatch
) -> None:
    async def fake_intent(question: str) -> QueryIntent:
        return QueryIntent(categoryKeywords=["계곡"], crowdPreference="quiet")

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    _override(db_session)
    try:
        res = await client.post("/v1/agent/ask", json={"question": "한적한 계곡"})
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    spots = res.json()["data"]["spots"]
    assert spots[0]["contentId"] == "v1"
    assert spots[0]["tag"] == "하위 25%"


@pytest.mark.integration
async def test_photo_query_applies_the_region_hint_inside_the_vector_query(
    db_session, client, seeded, monkeypatch
) -> None:
    for cid in ("v1", "j1"):
        await db_session.execute(
            text("INSERT INTO spot_embeddings (content_id, embedding) VALUES (:c, :v)"),
            {"c": cid, "v": _VEC},
        )
    await db_session.flush()

    async def fake_intent(question: str) -> QueryIntent:
        return QueryIntent(regionHints=["제주"])

    async def fake_embed(*, image_bytes, image_mime):
        return [0.1] * 512

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    monkeypatch.setattr(photo_service, "embed_photo", fake_embed)
    _override(db_session)
    try:
        res = await client.post(
            "/v1/agent/ask",
            files={"photo": ("a.jpg", b"x", "image/jpeg")},
            data={"question": "제주에서 이런 분위기"},
        )
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    data = res.json()["data"]
    assert [spot["contentId"] for spot in data["spots"]] == ["j1"]
    assert [step["tool"] for step in data["steps"]] == ["intent", "photo_match"]


@pytest.mark.integration
async def test_a_photo_that_matches_nothing_answers_with_zero_not_an_error(
    db_session, client, seeded, monkeypatch
) -> None:
    async def fake_intent(question: str) -> QueryIntent:
        return QueryIntent(regionHints=["제주"])

    async def fake_embed(*, image_bytes, image_mime):
        return [0.1] * 512

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    monkeypatch.setattr(photo_service, "embed_photo", fake_embed)
    _override(db_session)
    try:
        res = await client.post(
            "/v1/agent/ask",
            files={"photo": ("a.jpg", b"x", "image/jpeg")},
            data={"question": "제주에서 이런 분위기"},
        )
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    data = res.json()["data"]
    assert data["spots"] == []
    assert "없어요" in "".join(segment["text"] for segment in data["answer"])
    assert [chip["label"] for chip in data["refinements"]] == ["지역 넓히기"]
    assert data["steps"][-1]["badge"] == "0곳"


@pytest.mark.integration
async def test_photo_turn_hides_chips_whose_axis_the_photo_search_never_applies(
    db_session, client, seeded, monkeypatch
) -> None:
    await db_session.execute(
        text("INSERT INTO spot_embeddings (content_id, embedding) VALUES (:c, :v)"),
        {"c": "v1", "v": _VEC},
    )
    await db_session.flush()

    async def fake_embed(*, image_bytes, image_mime):
        return [0.1] * 512

    monkeypatch.setattr(photo_service, "embed_photo", fake_embed)
    _override(db_session)
    try:
        res = await client.post(
            "/v1/agent/ask",
            files={"photo": ("a.jpg", b"x", "image/jpeg")},
            data={
                "intent": json.dumps(
                    {"crowdPreference": "quiet", "categoryKeywords": ["계곡"]},
                )
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    data = res.json()["data"]
    assert data["spots"]
    assert data["suggestions"] == []


def test_photo_chips_cover_only_the_axes_the_photo_path_applies() -> None:
    chips = suggest_service.derive(
        QueryIntent(crowdPreference="quiet", categoryKeywords=["계곡"]),
        has_coords=True,
        result_count=2,
        axes=ask_service.PHOTO_AXES,
    )

    assert [c.label for c in chips] == ["가까운 순으로"]


@pytest.mark.integration
async def test_unmatched_category_keyword_falls_back_to_title_search(
    db_session, client, seeded, monkeypatch
) -> None:
    async def fake_intent(question: str) -> QueryIntent:
        return QueryIntent(categoryKeywords=["계곡-v2"])

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    _override(db_session)
    try:
        res = await client.post("/v1/agent/ask", json={"question": "계곡-v2"})
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    data = res.json()["data"]
    assert [step["tool"] for step in data["steps"]] == ["intent", "title_search"]
    assert data["spots"][0]["contentId"] == "v2"


@pytest.mark.integration
async def test_an_answer_does_not_claim_a_region_the_query_never_narrowed_to(
    db_session, client, seeded, monkeypatch
) -> None:
    async def fake_intent(question: str) -> QueryIntent:
        return QueryIntent(categoryKeywords=["계곡"], regionHints=["강남역"])

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    _override(db_session)
    try:
        res = await client.post("/v1/agent/ask", json={"question": "강남역 계곡"})
    finally:
        app.dependency_overrides.clear()

    data = res.json()["data"]
    assert data["spots"]
    assert "강남역" not in "".join(part["text"] for part in data["answer"])


@pytest.mark.integration
async def test_unmatched_keyword_with_no_title_hit_does_not_widen_to_everything(
    db_session, client, seeded, monkeypatch
) -> None:
    async def fake_intent(question: str) -> QueryIntent:
        return QueryIntent(categoryKeywords=["존재하지않는유형"])

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    _override(db_session)
    try:
        res = await client.post("/v1/agent/ask", json={"question": "존재하지않는유형"})
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    assert res.json()["data"]["spots"] == []


@pytest.mark.integration
async def test_title_fallback_does_not_claim_a_crowd_filter_it_never_ran(
    db_session, client, seeded, monkeypatch
) -> None:
    monkeypatch.setattr(
        intent_service,
        "extract_intent",
        _fake_intent(QueryIntent(categoryKeywords=["계곡-v2"], crowdPreference="quiet")),
    )
    _override(db_session)
    try:
        res = await client.post("/v1/agent/ask", json={"question": "조용한 계곡-v2"})
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    data = res.json()["data"]
    assert [step["tool"] for step in data["steps"]] == ["intent", "title_search"]
    assert "혼잡도로 추림" not in [step["label"] for step in data["steps"]]


@pytest.mark.integration
async def test_unresolved_keyword_with_a_mood_keeps_the_mood_axis(
    db_session, client, seeded, monkeypatch
) -> None:
    monkeypatch.setattr(
        intent_service,
        "extract_intent",
        _fake_intent(QueryIntent(categoryKeywords=["바닷가"], moodHints=["night"])),
    )
    _override(db_session)
    try:
        res = await client.post("/v1/agent/ask", json={"question": "야경 좋은 바닷가"})
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    data = res.json()["data"]
    assert [spot["contentId"] for spot in data["spots"]] == ["v1"]
    assert "mood_search" in [step["tool"] for step in data["steps"]]
    assert "title_search" not in [step["tool"] for step in data["steps"]]


@pytest.mark.integration
async def test_unresolved_keyword_with_indoor_keeps_the_indoor_axis(
    db_session, client, seeded, monkeypatch
) -> None:
    monkeypatch.setattr(
        intent_service,
        "extract_intent",
        _fake_intent(QueryIntent(categoryKeywords=["비 오는 날"], indoorOnly=True)),
    )
    _override(db_session)
    try:
        res = await client.post("/v1/agent/ask", json={"question": "비 오는 날 갈 곳"})
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    data = res.json()["data"]
    assert [spot["contentId"] for spot in data["spots"]] == ["m1"]
    assert "title_search" not in [step["tool"] for step in data["steps"]]


@pytest.mark.integration
async def test_named_place_without_the_mood_is_dropped_from_the_mood_search(
    db_session, client, seeded, monkeypatch
) -> None:
    monkeypatch.setattr(
        intent_service,
        "extract_intent",
        _fake_intent(
            QueryIntent(
                namedPlaces=[ExtractedPlace(name="계곡-v2", nameKo="계곡-v2")],
                moodHints=["night"],
            )
        ),
    )
    _override(db_session)
    try:
        res = await client.post("/v1/agent/ask", json={"question": "계곡-v2 같은 야경"})
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    data = res.json()["data"]
    assert [spot["contentId"] for spot in data["spots"]] == ["v1"]
    assert "mood_search" in [step["tool"] for step in data["steps"]]


@pytest.mark.integration
async def test_named_place_with_indoor_only_still_runs_the_indoor_search(
    db_session, client, seeded, monkeypatch
) -> None:
    monkeypatch.setattr(
        intent_service,
        "extract_intent",
        _fake_intent(
            QueryIntent(
                namedPlaces=[ExtractedPlace(name="계곡-v2", nameKo="계곡-v2")],
                indoorOnly=True,
            )
        ),
    )
    _override(db_session)
    try:
        res = await client.post("/v1/agent/ask", json={"question": "계곡-v2 말고 실내"})
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    data = res.json()["data"]
    assert [spot["contentId"] for spot in data["spots"]] == ["m1"]


@pytest.mark.integration
async def test_indoor_patch_drops_a_pinned_place_that_is_not_indoor(
    db_session, client, seeded
) -> None:
    _override(db_session)
    try:
        res = await client.post(
            "/v1/agent/ask",
            json={
                "intent": {"namedPlaces": [{"name": "계곡-v2", "nameKo": "계곡-v2"}]},
                "patch": {"indoorOnly": True},
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    data = res.json()["data"]
    assert data["intent"]["indoorOnly"] is True
    assert "v2" not in [spot["contentId"] for spot in data["spots"]]
    assert data["steps"][0] == {
        "tool": "resolve_place",
        "label": "질문 속 장소 확인",
        "badge": "0곳",
    }


@pytest.mark.integration
async def test_indoor_patch_keeps_a_pinned_place_that_is_indoor(db_session, client, seeded) -> None:
    await db_session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, addr1, "
            "first_image_url, show_flag, mapx, mapy, lcls_systm1, lcls_systm2, "
            "lcls_systm3, ldong_regn_cd, ldong_signgu_cd) "
            "VALUES ('a1', 14, '가덕도박물관', '부산광역시 사하구 5', "
            "'http://kto/i.jpg', 1, :lng, :lat, 'VE', 'VE07', 'VE070100', '26', '26380')"
        ),
        {"lng": LNG, "lat": LAT},
    )
    await db_session.flush()
    _override(db_session)
    try:
        res = await client.post(
            "/v1/agent/ask",
            json={
                "intent": {"namedPlaces": [{"name": "부산박물관", "nameKo": "부산박물관"}]},
                "patch": {"indoorOnly": True},
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    data = res.json()["data"]
    assert [spot["contentId"] for spot in data["spots"]] == ["m1", "a1"]


@pytest.mark.integration
async def test_quiet_patch_drops_a_pinned_place_that_is_crowded(db_session, client, seeded) -> None:
    _override(db_session)
    try:
        res = await client.post(
            "/v1/agent/ask",
            json={
                "intent": {"namedPlaces": [{"name": "계곡-v3", "nameKo": "계곡-v3"}]},
                "patch": {"crowdPreference": "quiet"},
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    data = res.json()["data"]
    assert data["intent"]["crowdPreference"] == "quiet"
    assert "v3" not in [spot["contentId"] for spot in data["spots"]]


@pytest.mark.integration
async def test_photo_query_survives_intent_extraction_failure(
    db_session, client, seeded, monkeypatch
) -> None:
    async def failing_intent(question: str) -> QueryIntent:
        raise AgentIntentUnavailable()

    async def fake_embed(*, image_bytes, image_mime):
        return [0.1] * 512

    async def fake_match(session, vector, *, region_prefixes):
        return [
            VectorMatchRow(
                content_id="v1",
                title="t-v1",
                category=None,
                addr1=None,
                lat=None,
                lng=None,
                image_url=None,
                cpyrht_div_cd=None,
                distance=0.2,
            )
        ]

    monkeypatch.setattr(intent_service, "extract_intent", failing_intent)
    monkeypatch.setattr(photo_service, "embed_photo", fake_embed)
    monkeypatch.setattr(photo_service, "match_vector", fake_match)
    _override(db_session)
    try:
        res = await client.post(
            "/v1/agent/ask",
            files={"photo": ("a.jpg", b"x", "image/jpeg")},
            data={"question": "이 사진 같은 분위기의 여행지"},
        )
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    data = res.json()["data"]
    assert [step["tool"] for step in data["steps"]] == ["photo_match"]
    assert data["spots"][0]["contentId"] == "v1"


@pytest.mark.integration
async def test_photo_upload_never_rolls_over_to_disk(
    db_session, client, seeded, monkeypatch
) -> None:
    rolled: list[int] = []
    real = tempfile.SpooledTemporaryFile

    def spy(*args, **kwargs):  # type: ignore[no-untyped-def]
        handle = real(*args, **kwargs)
        original = handle.rollover

        def rollover() -> None:
            rolled.append(1)
            original()

        handle.rollover = rollover  # type: ignore[method-assign]
        return handle

    async def fake_embed(*, image_bytes, image_mime):
        return [0.1] * 512

    async def fake_match(session, vector, *, region_prefixes):
        return [
            VectorMatchRow(
                content_id="v1",
                title="t-v1",
                category=None,
                addr1=None,
                lat=None,
                lng=None,
                image_url=None,
                cpyrht_div_cd=None,
                distance=0.2,
            )
        ]

    monkeypatch.setattr(formparsers, "SpooledTemporaryFile", spy)
    monkeypatch.setattr(photo_service, "embed_photo", fake_embed)
    monkeypatch.setattr(photo_service, "match_vector", fake_match)
    _override(db_session)
    try:
        res = await client.post(
            "/v1/agent/ask",
            files={"photo": ("a.jpg", b"x" * (4 * 1024 * 1024), "image/jpeg")},
        )
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    assert rolled == []


@pytest.mark.integration
async def test_oversized_body_is_rejected_before_parsing(db_session, client) -> None:
    _override(db_session)
    try:
        res = await client.post(
            "/v1/agent/ask",
            files={"photo": ("a.jpg", b"x" * (MAX_BODY_BYTES + 1), "image/jpeg")},
        )
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 422
    assert res.json()["error"]["code"] == "IMAGE_INVALID"


def test_multipart_spool_threshold_covers_the_accepted_upload_size() -> None:
    assert formparsers.MultiPartParser.spool_max_size >= MAX_BODY_BYTES


def test_crowd_filter_keeps_the_quiet_end_when_no_row_meets_the_threshold() -> None:
    rows = [_row(f"c{i}", rate=float(i), percentile=p) for i, p in enumerate((34, 67, 100))]

    kept = retrieve.filter_by_crowd(rows, "quiet")

    assert [row.content_id for row in kept] == ["c0", "c1", "c2"]
    assert kept[0].percentile == 34


def test_crowd_filter_keeps_the_popular_end_when_no_row_meets_the_threshold() -> None:
    rows = [_row(f"c{i}", rate=float(i), percentile=p) for i, p in enumerate((10, 20, 34))]

    kept = retrieve.filter_by_crowd(rows, "popular")

    assert [row.content_id for row in kept] == ["c2", "c1", "c0"]


@pytest.mark.integration
async def test_named_place_survives_an_empty_title_search(
    db_session, client, seeded, monkeypatch
) -> None:
    async def fake_intent(question: str) -> QueryIntent:
        return QueryIntent(
            categoryKeywords=["존재하지않는유형"],
            namedPlaces=[ExtractedPlace(name="계곡-v2", nameKo="계곡-v2")],
        )

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    _override(db_session)
    try:
        res = await client.post("/v1/agent/ask", json={"question": "계곡-v2 존재하지않는유형"})
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    assert [spot["contentId"] for spot in res.json()["data"]["spots"]] == ["v2"]


@pytest.mark.integration
async def test_empty_photo_upload_is_rejected_instead_of_falling_back_to_text(
    db_session, client, seeded, monkeypatch
) -> None:
    async def fake_intent(question: str) -> QueryIntent:
        raise AssertionError("text path must not run for an empty photo")

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    _override(db_session)
    try:
        res = await client.post(
            "/v1/agent/ask",
            files={"photo": ("a.jpg", b"", "image/jpeg")},
            data={"question": "계곡"},
        )
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 422
    assert res.json()["error"]["code"] == "IMAGE_INVALID"


@pytest.mark.integration
async def test_id_lookup_skips_hidden_and_imageless_spots(db_session, seeded) -> None:
    await db_session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, addr1, first_image_url, "
            "show_flag, lcls_systm1, ldong_regn_cd) "
            "VALUES ('hidden1', 12, '숨김', '부산광역시 사하구 2', 'http://kto/i.jpg', 0, "
            "'NA', '26')"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, addr1, first_image_url, "
            "show_flag, lcls_systm1, ldong_regn_cd) "
            "VALUES ('noimg1', 12, '사진없음', '부산광역시 사하구 3', '', 1, 'NA', '26')"
        )
    )
    await db_session.flush()

    found = await repositories.load_candidates_by_ids(db_session, ["v1", "hidden1", "noimg1"])

    assert set(found) == {"v1"}


@pytest.mark.integration
async def test_overseas_question_is_rejected_instead_of_recommending_random_domestic_spots(
    db_session, client, seeded, monkeypatch
) -> None:
    async def fake_intent(question: str) -> QueryIntent:
        return QueryIntent(outOfScope=True)

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    _override(db_session)
    try:
        res = await client.post("/v1/agent/ask", json={"question": "파리 여행지 추천"})
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 422
    assert res.json()["error"]["code"] == "AGENT_OUT_OF_SCOPE"


@pytest.mark.integration
async def test_supplied_out_of_scope_intent_is_rejected_on_a_refine_turn(
    db_session, client, seeded, monkeypatch
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(intent_service, "extract_intent", _forbidden_intent(calls))
    _override(db_session)
    try:
        res = await client.post(
            "/v1/agent/ask",
            json={
                "intent": {"outOfScope": True, "regionHints": ["파리"]},
                "patch": {"crowdPreference": "quiet"},
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 422
    assert res.json()["error"]["code"] == "AGENT_OUT_OF_SCOPE"
    assert calls == []


@pytest.mark.integration
async def test_photo_turn_stays_exempt_from_the_out_of_scope_guard(
    db_session, client, seeded, monkeypatch
) -> None:
    await db_session.execute(
        text("INSERT INTO spot_embeddings (content_id, embedding) VALUES (:c, :v)"),
        {"c": "v1", "v": _VEC},
    )
    await db_session.flush()

    async def fake_embed(*, image_bytes, image_mime):
        return [0.1] * 512

    monkeypatch.setattr(photo_service, "embed_photo", fake_embed)
    _override(db_session)
    try:
        res = await client.post(
            "/v1/agent/ask",
            files={"photo": ("a.jpg", b"x", "image/jpeg")},
            data={"intent": json.dumps({"outOfScope": True})},
        )
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    assert [spot["contentId"] for spot in res.json()["data"]["spots"]] == ["v1"]


@pytest.mark.integration
async def test_a_question_with_no_condition_asks_for_one_instead_of_dumping_the_country(
    db_session, client, seeded, monkeypatch
) -> None:
    async def fake_intent(question: str) -> QueryIntent:
        return QueryIntent()

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    _override(db_session)
    try:
        res = await client.post("/v1/agent/ask", json={"question": "어디 갈까"})
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    body = res.json()["data"]
    assert body["spots"] == []
    assert "".join(part["text"] for part in body["answer"]) == ask_service.NO_AXIS_ANSWER


@pytest.mark.integration
async def test_place_only_question_returns_the_place_without_a_nationwide_search(
    db_session, client, seeded, monkeypatch
) -> None:
    async def fake_intent(question: str) -> QueryIntent:
        return QueryIntent(namedPlaces=[ExtractedPlace(name="계곡-v2", nameKo="계곡-v2")])

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    _override(db_session)
    try:
        res = await client.post("/v1/agent/ask", json={"question": "계곡-v2"})
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    data = res.json()["data"]
    assert [step["tool"] for step in data["steps"]] == ["intent", "resolve_place"]
    assert [spot["contentId"] for spot in data["spots"]] == ["v2"]
    assert data["totalCount"] == 1


@pytest.mark.integration
async def test_place_only_question_fails_loudly_when_the_place_is_unresolvable(
    db_session, client, seeded, monkeypatch
) -> None:
    async def fake_intent(question: str) -> QueryIntent:
        return QueryIntent(namedPlaces=[ExtractedPlace(name="없는장소이름", nameKo="없는장소이름")])

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    _override(db_session)
    try:
        res = await client.post("/v1/agent/ask", json={"question": "없는장소이름"})
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 422
    assert res.json()["error"]["code"] == "AGENT_NO_RESULTS"


@pytest.mark.integration
async def test_title_search_queries_each_region_instead_of_filtering_after_the_limit(
    db_session, seeded
) -> None:
    found = await retrieve.search_by_title(db_session, ["계곡"], region_prefixes=["제주특별자치도"])

    assert [row.content_id for row in found] == ["j1"]


@pytest.mark.integration
async def test_quiet_threshold_is_applied_in_sql_before_the_limit(db_session, seeded) -> None:
    within = await repositories.find_candidates(
        db_session,
        codes=None,
        region_prefixes=None,
        limit=400,
        order="rate_asc",
        rated_only=True,
        percentile_ceiling=30,
    )

    assert [row.content_id for row in within] == ["v1"]
    assert within[0].percentile is not None and within[0].percentile <= 30


@pytest.mark.integration
async def test_near_with_quiet_still_filters_by_percentile_in_sql(
    db_session, client, seeded, monkeypatch
) -> None:
    async def fake_intent(question: str) -> QueryIntent:
        return QueryIntent(categoryKeywords=["계곡"], crowdPreference="quiet", nearMe=True)

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    _override(db_session)
    try:
        res = await client.post(
            "/v1/agent/ask",
            json={"question": "근처 한적한 계곡", "lat": LAT, "lng": LNG},
        )
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    assert [spot["contentId"] for spot in res.json()["data"]["spots"]] == ["v1"]


def test_a_search_lead_never_reports_a_zero_kilometre_distance() -> None:
    here = _row("c0", rate=10.0, percentile=10, lat=LAT, lng=LNG)

    segments = ask_service._answer(
        [here],
        intent=QueryIntent(nearMe=True),
        near=True,
        lat=LAT,
        lng=LNG,
    )

    text = "".join(s.text for s in segments)
    assert "0.0km" not in text
    assert "가장 가까운 곳이 10m예요." in text


@pytest.mark.integration
async def test_travel_predicate_surfaces_museums_that_the_map_predicate_drops(
    db_session, seeded
) -> None:
    rows = await repositories.find_candidates(
        db_session, codes=["VE070100"], region_prefixes=None, limit=50
    )

    assert [row.content_id for row in rows] == ["m1"]


@pytest.mark.integration
async def test_indoor_only_excludes_outdoor_experience_tourism(db_session, seeded) -> None:
    rows = await repositories.find_candidates(
        db_session, codes=None, region_prefixes=None, limit=50, indoor_only=True
    )

    ids = {row.content_id for row in rows}
    assert "m1" in ids
    assert "e1" not in ids


@pytest.mark.integration
async def test_indoor_with_an_outdoor_category_falls_back_to_indoor_only(
    db_session, client, seeded, monkeypatch
) -> None:
    async def fake_intent(question: str) -> QueryIntent:
        return QueryIntent(categoryKeywords=["계곡"], indoorOnly=True)

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    _override(db_session)
    try:
        res = await client.post("/v1/agent/ask", json={"question": "실내 계곡"})
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    data = res.json()["data"]
    assert [step["tool"] for step in data["steps"]] == [
        "intent",
        "category_search",
        "category_search",
    ]
    assert data["steps"][1]["badge"] == "0곳"
    assert data["steps"][2]["label"] == ask_service.INDOOR_RETRY_LABEL
    assert [spot["contentId"] for spot in data["spots"]] == ["m1"]


@pytest.mark.integration
async def test_indoor_fallback_echoes_an_intent_without_the_category_it_dropped(
    db_session, client, seeded, monkeypatch
) -> None:
    async def fake_intent(question: str) -> QueryIntent:
        return QueryIntent(categoryKeywords=["계곡"], indoorOnly=True)

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    _override(db_session)
    try:
        res = await client.post("/v1/agent/ask", json={"question": "실내 계곡"})
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    data = res.json()["data"]
    assert [spot["contentId"] for spot in data["spots"]] == ["m1"]
    assert data["intent"]["categoryKeywords"] == []
    assert data["intent"]["indoorOnly"] is True


@pytest.mark.integration
async def test_indoor_with_an_indoor_category_narrows_without_falling_back(
    db_session, client, seeded, monkeypatch
) -> None:
    await db_session.execute(
        text(
            "INSERT INTO lcls_systm_codes "
            "(lcls_systm3_cd, lcls_systm2_cd, lcls_systm1_cd, lcls_systm3_nm, "
            "lcls_systm2_nm, lcls_systm1_nm) "
            "VALUES ('VE060100', 'VE06', 'VE', '공연장', '공연시설', '문화관광') "
            "ON CONFLICT DO NOTHING"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, addr1, "
            "first_image_url, show_flag, mapx, mapy, lcls_systm1, lcls_systm2, "
            "lcls_systm3, ldong_regn_cd, ldong_signgu_cd) "
            "VALUES ('p1', 14, '부산공연장', '부산광역시 사하구 4', "
            "'http://kto/i.jpg', 1, :lng, :lat, 'VE', 'VE06', 'VE060100', '26', '26380')"
        ),
        {"lng": LNG, "lat": LAT},
    )
    await db_session.flush()

    async def fake_intent(question: str) -> QueryIntent:
        return QueryIntent(categoryKeywords=["박물관"], indoorOnly=True)

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    _override(db_session)
    try:
        res = await client.post("/v1/agent/ask", json={"question": "실내 박물관"})
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    data = res.json()["data"]
    assert [step["tool"] for step in data["steps"]] == ["intent", "category_search"]
    assert [spot["contentId"] for spot in data["spots"]] == ["m1"]
    assert data["intent"]["categoryKeywords"] == ["박물관"]


@pytest.mark.integration
async def test_mood_codes_resolve_to_ids(db_session, seeded) -> None:
    night = await repositories.find_mood_ids(db_session, ["night"])

    assert len(night) == 1
    assert await repositories.find_mood_ids(db_session, ["island", "night"]) != night
    assert await repositories.find_mood_ids(db_session, []) == []
    assert await repositories.find_mood_ids(db_session, ["nope"]) == []


@pytest.mark.integration
async def test_mood_filter_narrows_candidates(db_session, seeded) -> None:
    night = await repositories.find_mood_ids(db_session, ["night"])

    rows = await repositories.find_candidates(
        db_session, codes=None, region_prefixes=None, limit=50, mood_ids=night
    )

    assert [row.content_id for row in rows] == ["v1"]


def test_intent_parses_mood_hints_and_drops_unknown_codes() -> None:
    parsed = intent_service._moods(["night", "sea", "market", 7, "night"])

    assert parsed == ["night", "sea"]


def _fake_intent(intent: QueryIntent) -> Callable[[str], Awaitable[QueryIntent]]:
    async def run(question: str) -> QueryIntent:
        return intent

    return run


@pytest.mark.integration
async def test_mood_hint_filters_the_candidate_pool(
    db_session, client, seeded, monkeypatch
) -> None:
    monkeypatch.setattr(
        intent_service,
        "extract_intent",
        _fake_intent(QueryIntent(moodHints=["night"])),
    )
    _override(db_session)
    try:
        res = await client.post("/v1/agent/ask", json={"question": "야경 좋은 곳"})
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    data = res.json()["data"]
    assert [spot["contentId"] for spot in data["spots"]] == ["v1"]
    assert any(step["tool"] == "mood_search" for step in data["steps"])


@pytest.mark.integration
async def test_unknown_mood_codes_leave_the_pool_unfiltered(
    db_session, client, seeded, monkeypatch
) -> None:
    monkeypatch.setattr(
        intent_service,
        "extract_intent",
        _fake_intent(QueryIntent(categoryKeywords=["계곡"])),
    )
    _override(db_session)
    try:
        res = await client.post("/v1/agent/ask", json={"question": "계곡"})
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    data = res.json()["data"]
    assert [step["tool"] for step in data["steps"]] == ["intent", "category_search"]


def test_intent_response_schema_matches_the_parsed_fields() -> None:
    schema = intent_service._RESPONSE_SCHEMA
    required = set(schema["required"])

    assert {"moodHints", "festivalOnly"} <= set(schema["properties"])
    assert {"moodHints", "festivalOnly"} <= required
    assert required <= set(QueryIntent.model_fields)
    assert set(schema["properties"]) <= set(QueryIntent.model_fields)
    assert schema["properties"]["moodHints"]["items"]["enum"] == list(intent_service._MOOD_CODES)


def test_every_mood_literal_reaches_the_intent_untouched() -> None:
    codes = list(get_args(Mood))

    assert intent_service._moods(codes) == codes
    assert QueryIntent(moodHints=codes).moodHints == codes


def test_apply_patch_sets_only_the_named_axes() -> None:
    base = QueryIntent(categoryKeywords=["계곡"], regionHints=["제주"])

    result = refine_service.apply_patch(base, RefinePatch(crowdPreference="quiet"))

    assert result.crowdPreference == "quiet"
    assert result.categoryKeywords == ["계곡"]
    assert result.regionHints == ["제주"]


def test_apply_patch_drop_clears_the_named_axis() -> None:
    base = QueryIntent(
        categoryKeywords=["계곡"],
        moodHints=["sea"],
        regionHints=["제주"],
        crowdPreference="quiet",
        indoorOnly=True,
        nearMe=True,
    )

    assert refine_service.apply_patch(base, RefinePatch(drop="crowd")).crowdPreference == "any"
    assert refine_service.apply_patch(base, RefinePatch(drop="region")).regionHints == []
    assert refine_service.apply_patch(base, RefinePatch(drop="indoor")).indoorOnly is False
    assert refine_service.apply_patch(base, RefinePatch(drop="near")).nearMe is False

    dropped = refine_service.apply_patch(base, RefinePatch(drop="category"))
    assert dropped.categoryKeywords == []
    assert dropped.moodHints == []


def test_apply_patch_with_no_patch_returns_the_intent_unchanged() -> None:
    base = QueryIntent(categoryKeywords=["계곡"])

    assert refine_service.apply_patch(base, None) == base


def test_apply_patch_never_writes_none_over_a_non_optional_axis() -> None:
    base = QueryIntent(crowdPreference="quiet", indoorOnly=True, nearMe=True)

    result = refine_service.apply_patch(base, RefinePatch())

    assert result.crowdPreference == "quiet"
    assert result.indoorOnly is True
    assert result.nearMe is True


def _forbidden_intent(calls: list[str]) -> Callable[[str], Awaitable[QueryIntent]]:
    async def run(question: str) -> QueryIntent:
        calls.append(question)
        raise AssertionError("LLM must not be called on a refine request")

    return run


@pytest.mark.integration
async def test_refine_request_skips_the_llm_and_keeps_prior_axes(
    db_session, client, seeded, monkeypatch
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(intent_service, "extract_intent", _forbidden_intent(calls))
    _override(db_session)
    try:
        res = await client.post(
            "/v1/agent/ask",
            json={
                "intent": {"categoryKeywords": ["계곡"], "regionHints": ["부산"]},
                "patch": {"crowdPreference": "quiet"},
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    assert calls == []
    data = res.json()["data"]
    assert data["intent"]["crowdPreference"] == "quiet"
    assert data["intent"]["categoryKeywords"] == ["계곡"]
    assert data["intent"]["regionHints"] == ["부산"]
    assert [step["tool"] for step in data["steps"]] == ["category_search", "concentration"]
    assert [spot["contentId"] for spot in data["spots"]] == ["v1", "v2", "v3"]
    assert [chip["label"] for chip in data["refinements"]] == ["유명한 곳으로"]


@pytest.mark.integration
async def test_intent_wins_over_a_question_instead_of_re_extracting(
    db_session, client, seeded, monkeypatch
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(intent_service, "extract_intent", _forbidden_intent(calls))
    _override(db_session)
    try:
        res = await client.post(
            "/v1/agent/ask",
            json={
                "question": "더 한적한 곳",
                "intent": {"categoryKeywords": ["계곡"], "regionHints": ["제주"]},
                "patch": {"crowdPreference": "quiet"},
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    assert calls == []
    data = res.json()["data"]
    assert data["intent"]["regionHints"] == ["제주"]
    assert [spot["contentId"] for spot in data["spots"]] == ["j1"]


@pytest.mark.integration
async def test_photo_refine_reads_the_multipart_intent_and_skips_the_llm(
    db_session, client, seeded, monkeypatch
) -> None:
    for cid in ("v1", "j1"):
        await db_session.execute(
            text("INSERT INTO spot_embeddings (content_id, embedding) VALUES (:c, :v)"),
            {"c": cid, "v": _VEC},
        )
    await db_session.flush()

    calls: list[str] = []

    async def fake_embed(*, image_bytes, image_mime):
        return [0.1] * 512

    monkeypatch.setattr(intent_service, "extract_intent", _forbidden_intent(calls))
    monkeypatch.setattr(photo_service, "embed_photo", fake_embed)
    _override(db_session)
    try:
        res = await client.post(
            "/v1/agent/ask",
            files={"photo": ("a.jpg", b"x", "image/jpeg")},
            data={
                "question": "이런 분위기",
                "intent": json.dumps({"regionHints": ["제주"]}),
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    assert calls == []
    data = res.json()["data"]
    assert [step["tool"] for step in data["steps"]] == ["photo_match"]
    assert [spot["contentId"] for spot in data["spots"]] == ["j1"]
    assert data["intent"]["regionHints"] == ["제주"]
    assert data["refinements"] == []


@pytest.mark.integration
async def test_suggestions_stay_plain_labels_of_the_refinements(
    db_session, client, seeded_wide, monkeypatch
) -> None:
    async def fake_intent(question: str) -> QueryIntent:
        return QueryIntent(categoryKeywords=["계곡"], regionHints=["부산"])

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    _override(db_session)
    try:
        res = await client.post("/v1/agent/ask", json={"question": "부산 계곡"})
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    data = res.json()["data"]
    assert data["refinements"]
    assert all(chip["patch"]["drop"] is None for chip in data["refinements"])
    assert all(isinstance(label, str) for label in data["suggestions"])
    assert data["suggestions"] == [chip["label"] for chip in data["refinements"]]


@pytest.mark.integration
async def test_a_result_turn_carries_no_condition_release_chip(
    db_session, client, seeded, monkeypatch
) -> None:
    monkeypatch.setattr(intent_service, "extract_intent", _forbidden_intent([]))
    _override(db_session)
    try:
        res = await client.post(
            "/v1/agent/ask",
            json={
                "intent": {"categoryKeywords": ["계곡"], "regionHints": ["부산"]},
                "patch": {"crowdPreference": "quiet"},
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    data = res.json()["data"]
    assert [chip for chip in data["refinements"] if chip["patch"]["drop"] is not None] == []
    assert data["suggestions"] == [chip["label"] for chip in data["refinements"]]


@pytest.mark.integration
async def test_photo_suggestions_stay_plain_labels_of_the_refinements(
    db_session, client, seeded, monkeypatch
) -> None:
    for cid in ("v1", "j1"):
        await db_session.execute(
            text("INSERT INTO spot_embeddings (content_id, embedding) VALUES (:c, :v)"),
            {"c": cid, "v": _VEC},
        )
    await db_session.flush()

    async def fake_embed(*, image_bytes, image_mime):
        return [0.1] * 512

    monkeypatch.setattr(intent_service, "extract_intent", _forbidden_intent([]))
    monkeypatch.setattr(photo_service, "embed_photo", fake_embed)
    _override(db_session)
    try:
        res = await client.post(
            "/v1/agent/ask",
            files={"photo": ("a.jpg", b"x", "image/jpeg")},
            data={
                "intent": json.dumps({"regionHints": ["제주"]}),
                "lat": str(LAT),
                "lng": str(LNG),
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    data = res.json()["data"]
    assert data["refinements"]
    assert all(isinstance(label, str) for label in data["suggestions"])
    assert data["suggestions"] == [chip["label"] for chip in data["refinements"]]


@pytest.mark.integration
async def test_multipart_intent_that_is_not_json_is_rejected(db_session, client) -> None:
    _override(db_session)
    try:
        res = await client.post(
            "/v1/agent/ask",
            files={"photo": ("a.jpg", b"x", "image/jpeg")},
            data={"intent": "not-json"},
        )
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 422
    assert res.json()["error"]["code"] == "VALIDATION_FAILED"


def test_intent_list_caps_accept_a_full_extraction_and_reject_more() -> None:
    assert len(QueryIntent(categoryKeywords=["k"] * MAX_KEYWORDS).categoryKeywords) == MAX_KEYWORDS
    assert len(QueryIntent(regionHints=["r"] * MAX_REGION_HINTS).regionHints) == MAX_REGION_HINTS

    with pytest.raises(ValidationError):
        QueryIntent(categoryKeywords=["k"] * (MAX_KEYWORDS + 1))
    with pytest.raises(ValidationError):
        QueryIntent(regionHints=["r"] * (MAX_REGION_HINTS + 1))
    with pytest.raises(ValidationError):
        QueryIntent(namedPlaces=[ExtractedPlace(name="p")] * (MAX_NAMED_PLACES + 1))
    with pytest.raises(ValidationError):
        QueryIntent(moodHints=["sea"] * 8)


def test_intent_string_caps_accept_a_long_place_name_and_reject_longer() -> None:
    longest = "가" * MAX_TEXT_CHARS
    over = "가" * (MAX_TEXT_CHARS + 1)

    assert QueryIntent(regionHints=[longest]).regionHints == [longest]
    assert ExtractedPlace(name=longest, regionHint=longest, tip=longest).name == longest

    with pytest.raises(ValidationError):
        QueryIntent(regionHints=[over])
    with pytest.raises(ValidationError):
        QueryIntent(categoryKeywords=[over])
    with pytest.raises(ValidationError):
        ExtractedPlace(name=over)
    with pytest.raises(ValidationError):
        ExtractedPlace(name="속초해수욕장", regionHint=over)
    with pytest.raises(ValidationError):
        ExtractedPlace(name="속초해수욕장", nameKo=over)


class _RegionRow:
    def __init__(self, sido: str, sigungu: str | None, tier: int) -> None:
        self.sido = sido
        self.sigungu = sigungu
        self.tier = tier


class _RegionResult:
    def __init__(self, rows: list[_RegionRow]) -> None:
        self._rows = rows

    def all(self) -> list[_RegionRow]:
        return self._rows


class _RegionSession:
    def __init__(self, by_token: dict[str, list[_RegionRow]]) -> None:
        self._by_token = by_token
        self.tokens: list[str] = []

    async def execute(self, statement: object, params: dict[str, str]) -> _RegionResult:
        token = params["tok"]
        self.tokens.append(token)
        return _RegionResult(self._by_token.get(token, []))


async def test_a_sigungu_token_resolves_to_a_sigungu_qualified_prefix() -> None:
    session = _RegionSession({"경주": [_RegionRow("경상북도", "경주시", 2)]})

    mapping = await map_region_tokens_to_prefixes(session, {"경주"})

    assert mapping["경주"].prefix == "경상북도 경주시"
    assert mapping["경주"].sido == "경상북도"
    assert mapping["경주"].narrowed is True


async def test_a_sido_token_outranks_a_same_named_sigungu() -> None:
    session = _RegionSession(
        {"제주": [_RegionRow("제주특별자치도", None, 1), _RegionRow("제주특별자치도", "제주시", 2)]}
    )

    mapping = await map_region_tokens_to_prefixes(session, {"제주"})

    assert mapping["제주"].prefix == "제주특별자치도"
    assert mapping["제주"].narrowed is False


async def test_the_everyday_spelling_of_a_sido_still_resolves() -> None:
    session = _RegionSession({"제주": [_RegionRow("제주특별자치도", None, 1)]})

    mapping = await map_region_tokens_to_prefixes(session, {"제주도"})

    assert mapping["제주도"].prefix == "제주특별자치도"


async def test_a_renamed_province_resolves_from_its_old_name() -> None:
    session = _RegionSession({"강원": [_RegionRow("강원특별자치도", None, 1)]})

    mapping = await map_region_tokens_to_prefixes(session, {"강원도"})

    assert mapping["강원도"].prefix == "강원특별자치도"


async def test_a_metropolitan_city_resolves_from_the_short_city_spelling() -> None:
    session = _RegionSession({"서울": [_RegionRow("서울특별시", None, 1)]})

    mapping = await map_region_tokens_to_prefixes(session, {"서울시"})

    assert mapping["서울시"].prefix == "서울특별시"


async def test_an_ambiguous_city_spelling_is_left_alone() -> None:
    session = _RegionSession({"광주시": [_RegionRow("경기도", "광주시", 2)]})

    mapping = await map_region_tokens_to_prefixes(session, {"광주시"})

    assert mapping["광주시"].prefix == "경기도 광주시"


async def test_two_character_province_names_resolve() -> None:
    session = _RegionSession(
        {
            "충청북": [_RegionRow("충청북도", None, 1)],
            "경상남": [_RegionRow("경상남도", None, 1)],
            "전라남": [_RegionRow("전라남도", None, 1)],
        }
    )

    mapping = await map_region_tokens_to_prefixes(session, {"충북", "경남", "전남"})

    assert mapping["충북"].prefix == "충청북도"
    assert mapping["경남"].prefix == "경상남도"
    assert mapping["전남"].prefix == "전라남도"


async def test_a_city_split_into_districts_resolves_to_the_city() -> None:
    session = _RegionSession(
        {
            "전주": [
                _RegionRow("전북특별자치도", "전주시완산구", 2),
                _RegionRow("전북특별자치도", "전주시덕진구", 2),
            ]
        }
    )

    mapping = await map_region_tokens_to_prefixes(session, {"전주"})

    assert mapping["전주"].prefix == "전북특별자치도 전주시"
    assert mapping["전주"].sido == "전북특별자치도"
    assert mapping["전주"].narrowed is True


async def test_a_same_named_district_in_two_provinces_still_resolves_to_nothing() -> None:
    session = _RegionSession(
        {"고성": [_RegionRow("강원특별자치도", "고성군", 2), _RegionRow("경상남도", "고성군", 2)]}
    )

    assert await map_region_tokens_to_prefixes(session, {"고성"}) == {}


async def test_unrelated_districts_in_one_province_do_not_merge() -> None:
    session = _RegionSession(
        {"남": [_RegionRow("부산광역시", "남구", 2), _RegionRow("부산광역시", "동구", 2)]}
    )

    assert await map_region_tokens_to_prefixes(session, {"남"}) == {}


async def test_an_ambiguous_sigungu_token_resolves_to_nothing() -> None:
    session = _RegionSession(
        {"중구": [_RegionRow("서울특별시", "중구", 2), _RegionRow("부산광역시", "중구", 2)]}
    )

    assert await map_region_tokens_to_prefixes(session, {"중구"}) == {}


async def test_an_ambiguous_sido_token_resolves_to_nothing() -> None:
    session = _RegionSession(
        {"충청": [_RegionRow("충청남도", None, 1), _RegionRow("충청북도", None, 1)]}
    )

    assert await map_region_tokens_to_prefixes(session, {"충청"}) == {}


async def test_resolving_a_region_costs_one_query_per_token() -> None:
    session = _RegionSession({"경주": [_RegionRow("경상북도", "경주시", 2)]})

    await map_region_tokens_to_prefixes(session, {"경주", "여수"})

    assert len(session.tokens) == 2


async def test_a_narrowed_scope_reports_the_sido_it_can_widen_to() -> None:
    session = _RegionSession({"경주": [_RegionRow("경상북도", "경주시", 2)]})

    scope = await retrieve.resolve_region_scope(session, hints=["경주"])

    assert scope.prefixes == ["경상북도 경주시"]
    assert scope.sido_prefixes == ["경상북도"]
    assert scope.narrowed_hints == ("경주",)
    assert scope.widenable is True


async def test_a_sido_prefix_cannot_swallow_the_sigungu_it_contains() -> None:
    session = _RegionSession(
        {
            "경상북도": [_RegionRow("경상북도", None, 1)],
            "경주시": [_RegionRow("경상북도", "경주시", 2)],
        }
    )

    scope = await retrieve.resolve_region_scope(session, hints=["경상북도 경주시"])

    assert scope.prefixes == ["경상북도 경주시"]
    assert scope.sido_prefixes == ["경상북도"]
    assert scope.widenable is True


async def test_two_unrelated_regions_both_survive() -> None:
    session = _RegionSession(
        {
            "부산": [_RegionRow("부산광역시", None, 1)],
            "제주": [_RegionRow("제주특별자치도", None, 1)],
        }
    )

    scope = await retrieve.resolve_region_scope(session, hints=["부산", "제주"])

    assert scope.prefixes == ["부산광역시", "제주특별자치도"]


async def test_a_sido_scope_is_not_widenable() -> None:
    session = _RegionSession({"제주": [_RegionRow("제주특별자치도", None, 1)]})

    scope = await retrieve.resolve_region_scope(session, hints=["제주"])

    assert scope.prefixes == ["제주특별자치도"]
    assert scope.widenable is False


class _CountingResult:
    def all(self) -> list[object]:
        return []


class _CountingSession:
    def __init__(self) -> None:
        self.calls = 0

    async def execute(self, statement: object, params: object = None) -> _CountingResult:
        self.calls += 1
        return _CountingResult()


async def test_one_region_hint_cannot_fan_out_into_a_query_per_word() -> None:
    session = _CountingSession()

    await retrieve.resolve_region_prefixes(session, hints=[" ".join(f"제{i}" for i in range(40))])

    assert session.calls <= MAX_HINT_TOKENS + 1


async def test_a_full_region_hint_list_stays_within_the_region_token_budget() -> None:
    session = _CountingSession()
    hints = [" ".join(f"제{i}{j}" for j in range(40)) for i in range(MAX_REGION_HINTS)]

    await retrieve.resolve_region_prefixes(session, hints=hints)

    assert session.calls <= MAX_REGION_TOKENS


def test_a_place_region_hint_cannot_fan_out_into_a_token_per_word() -> None:
    tokens = resolve_service._hint_tokens(" ".join(f"제{i}" for i in range(40)))

    assert len(tokens) <= MAX_HINT_TOKENS + 1


async def test_region_token_lookup_caps_its_own_db_round_trips() -> None:
    session = _CountingSession()

    await map_region_tokens_to_sido(session, {f"토큰{i}" for i in range(MAX_REGION_TOKENS * 5)})

    assert session.calls == MAX_REGION_TOKENS


@pytest.mark.integration
async def test_over_long_region_hints_are_rejected_before_any_region_lookup(
    db_session, client, monkeypatch
) -> None:
    calls: list[str] = []

    async def boom_prefixes(session, *, hints):
        raise AssertionError("an over-cap intent must not reach the region lookup")

    monkeypatch.setattr(intent_service, "extract_intent", _forbidden_intent(calls))
    monkeypatch.setattr(retrieve, "resolve_region_prefixes", boom_prefixes)
    _override(db_session)
    try:
        res = await client.post(
            "/v1/agent/ask",
            json={"intent": {"regionHints": ["제주 " * 100]}},
        )
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 422
    assert res.json()["error"]["code"] == "VALIDATION_FAILED"
    assert calls == []


@pytest.mark.integration
async def test_over_long_named_place_name_is_rejected_before_the_naver_fanout(
    db_session, client, monkeypatch
) -> None:
    async def boom_resolve(session, kto, places):
        raise AssertionError("an over-cap intent must not reach the place resolver")

    monkeypatch.setattr(resolve_service, "resolve_places", boom_resolve)
    _override(db_session)
    try:
        res = await client.post(
            "/v1/agent/ask",
            json={"intent": {"namedPlaces": [{"name": "가" * (MAX_TEXT_CHARS + 1)}]}},
        )
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 422
    assert res.json()["error"]["code"] == "VALIDATION_FAILED"


@pytest.mark.integration
async def test_over_long_category_keywords_are_rejected_before_any_search(
    db_session, client, monkeypatch
) -> None:
    calls: list[str] = []

    async def boom_codes(session, keywords):
        raise AssertionError("an over-cap intent must not reach the category search")

    monkeypatch.setattr(intent_service, "extract_intent", _forbidden_intent(calls))
    monkeypatch.setattr(retrieve, "resolve_category_codes", boom_codes)
    _override(db_session)
    try:
        res = await client.post(
            "/v1/agent/ask",
            json={"intent": {"categoryKeywords": ["계곡"] * (MAX_KEYWORDS + 1)}},
        )
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 422
    assert res.json()["error"]["code"] == "VALIDATION_FAILED"
    assert calls == []


@pytest.mark.integration
async def test_over_long_named_places_are_rejected_before_the_naver_fanout(
    db_session, client, monkeypatch
) -> None:
    async def boom_resolve(session, kto, places):
        raise AssertionError("an over-cap intent must not reach the place resolver")

    monkeypatch.setattr(resolve_service, "resolve_places", boom_resolve)
    _override(db_session)
    try:
        res = await client.post(
            "/v1/agent/ask",
            json={
                "intent": {"namedPlaces": [{"name": f"p{i}"} for i in range(MAX_NAMED_PLACES + 1)]}
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 422
    assert res.json()["error"]["code"] == "VALIDATION_FAILED"


async def test_extract_intent_truncates_a_chatty_llm_instead_of_failing(monkeypatch) -> None:
    class FakeClient:
        async def generate_json(self, **kwargs):
            return {
                "categoryKeywords": [
                    f"k{i}" + "설" * MAX_TEXT_CHARS for i in range(MAX_KEYWORDS + 5)
                ],
                "regionHints": [
                    f"r{i}" + "설" * MAX_TEXT_CHARS for i in range(MAX_REGION_HINTS + 5)
                ],
                "namedPlaces": [
                    {
                        "name": f"p{i}" + "설" * MAX_TEXT_CHARS,
                        "regionHint": "설" * MAX_TEXT_CHARS * 2,
                        "placeType": "attraction",
                    }
                    for i in range(MAX_NAMED_PLACES + 5)
                ],
            }

    monkeypatch.setattr(llm, "get_client", FakeClient)

    parsed = await intent_service.extract_intent("아무 질문")

    assert len(parsed.categoryKeywords) == MAX_KEYWORDS
    assert len(parsed.regionHints) == MAX_REGION_HINTS
    assert len(parsed.namedPlaces) == MAX_NAMED_PLACES
    assert max(len(k) for k in parsed.categoryKeywords) == MAX_TEXT_CHARS
    assert max(len(r) for r in parsed.regionHints) == MAX_TEXT_CHARS
    assert all(len(p.name) == MAX_TEXT_CHARS for p in parsed.namedPlaces)


@pytest.mark.integration
async def test_legacy_region_still_filters_while_when_and_who_stay_ignored(
    db_session, client, seeded, monkeypatch
) -> None:
    async def fake_intent(question: str) -> QueryIntent:
        return QueryIntent(categoryKeywords=["계곡"])

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    _override(db_session)
    try:
        res = await client.post(
            "/v1/agent/ask",
            json={"question": "계곡", "region": "jeju", "when": "weekend", "who": "pets"},
        )
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    data = res.json()["data"]
    assert [spot["contentId"] for spot in data["spots"]] == ["j1"]
    assert "이번 주말" not in "".join(seg["text"] for seg in data["answer"])


@pytest.mark.integration
async def test_legacy_region_yields_to_a_region_the_question_names(
    db_session, client, seeded, monkeypatch
) -> None:
    async def fake_intent(question: str) -> QueryIntent:
        return QueryIntent(categoryKeywords=["계곡"], regionHints=["부산"])

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    _override(db_session)
    try:
        res = await client.post(
            "/v1/agent/ask",
            json={"question": "부산 계곡", "region": "jeju"},
        )
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    assert [spot["contentId"] for spot in res.json()["data"]["spots"]] == ["v1", "v2", "v3"]


@pytest.mark.integration
async def test_legacy_region_narrows_a_photo_query_too(
    db_session, client, seeded, monkeypatch
) -> None:
    seen: list[list[str]] = []

    async def fake_embed(*, image_bytes, image_mime):
        return [0.1] * 512

    async def fake_match(session, vector, *, region_prefixes):
        seen.append(region_prefixes)
        return [
            VectorMatchRow(
                content_id="j1",
                title="제주계곡",
                category=None,
                addr1=None,
                lat=None,
                lng=None,
                image_url=None,
                cpyrht_div_cd=None,
                distance=0.2,
            )
        ]

    monkeypatch.setattr(photo_service, "embed_photo", fake_embed)
    monkeypatch.setattr(photo_service, "match_vector", fake_match)
    _override(db_session)
    try:
        res = await client.post(
            "/v1/agent/ask",
            files={"photo": ("a.jpg", b"x" * 32, "image/jpeg")},
            data={"region": "jeju", "when": "weekend", "who": "pets"},
        )
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    assert seen == [["제주"]]


@pytest.mark.integration
async def test_legacy_region_all_stays_nationwide(db_session, client, seeded, monkeypatch) -> None:
    async def fake_intent(question: str) -> QueryIntent:
        return QueryIntent(categoryKeywords=["계곡"])

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    _override(db_session)
    try:
        res = await client.post("/v1/agent/ask", json={"question": "계곡", "region": "all"})
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    assert [spot["contentId"] for spot in res.json()["data"]["spots"]] == ["j1", "v1", "v2", "v3"]


def test_suggestions_offer_only_axes_that_are_not_already_on() -> None:
    chips = suggest_service.derive(
        QueryIntent(crowdPreference="quiet", indoorOnly=True),
        has_coords=False,
        result_count=20,
    )

    assert [c.label for c in chips] == ["유명한 곳으로"]
    assert chips[0].patch == RefinePatch(crowdPreference="popular")


def test_suggestions_offer_distance_only_when_coords_are_present() -> None:
    without = suggest_service.derive(QueryIntent(), has_coords=False, result_count=20)
    with_coords = suggest_service.derive(QueryIntent(), has_coords=True, result_count=20)

    assert "가까운 순으로" not in [c.label for c in without]
    assert "가까운 순으로" in [c.label for c in with_coords]
    assert [c.label for c in without] == ["사람 적은 곳만", "실내만"]
    assert [c.patch for c in with_coords] == [
        RefinePatch(crowdPreference="quiet"),
        RefinePatch(indoorOnly=True),
        RefinePatch(nearMe=True),
    ]


def test_suggestions_drop_the_distance_axis_once_near_me_is_on() -> None:
    chips = suggest_service.derive(QueryIntent(nearMe=True), has_coords=True, result_count=20)

    assert [c.label for c in chips] == ["사람 적은 곳만", "실내만"]


def test_a_thin_turn_offers_no_condition_release_chip() -> None:
    chips = suggest_service.derive(
        QueryIntent(crowdPreference="quiet", regionHints=["제주"]),
        has_coords=False,
        result_count=2,
    )

    assert [c.label for c in chips] == ["유명한 곳으로", "실내만"]
    assert all(c.patch.drop is None for c in chips)


def test_result_chips_do_not_depend_on_how_thin_the_result_is() -> None:
    thin = suggest_service.derive(
        QueryIntent(crowdPreference="quiet", regionHints=["제주"]),
        has_coords=False,
        result_count=2,
    )
    ample = suggest_service.derive(
        QueryIntent(crowdPreference="quiet", regionHints=["제주"]),
        has_coords=False,
        result_count=20,
    )

    assert [c.label for c in thin] == [c.label for c in ample]


def test_festival_turns_get_no_follow_up_chips() -> None:
    chips = suggest_service.derive(QueryIntent(festivalOnly=True), has_coords=True, result_count=10)

    assert chips == []


def test_suggestions_are_capped_at_three() -> None:
    chips = suggest_service.derive(
        QueryIntent(regionHints=["제주"]), has_coords=True, result_count=2
    )

    assert len(chips) == 3
    assert [c.label for c in chips] == ["사람 적은 곳만", "실내만", "가까운 순으로"]


class _StubKto:
    async def call(self, *args: object, **kwargs: object) -> list[dict]:
        return []


def _override_with_kto(db_session: AsyncSession) -> None:
    _override(db_session)
    app.dependency_overrides[get_kto] = lambda: _StubKto()


def _festival_card(content_id: str, *, title: str, region_label: str, dday: str) -> ChannelCardRow:
    return ChannelCardRow(
        content_id=content_id,
        title=title,
        region_label=region_label,
        image_url="https://kto/f.jpg",
        dday=dday,
        line="8월 2일까지",
        cpyrht_div_cd="Type3",
    )


def _festival_pool(cards: list[ChannelCardRow]) -> Callable[..., Awaitable[list[ChannelCardRow]]]:
    async def load(
        redis: object, kto: object, *, fetch_timeout: float | None = None
    ) -> list[ChannelCardRow]:
        return cards

    return load


async def _seed_festival_spots(session: AsyncSession, content_ids: list[str]) -> None:
    for cid in content_ids:
        await session.execute(
            text(
                "INSERT INTO spots (content_id, content_type_id, title, addr1, "
                "first_image_url, show_flag) "
                "VALUES (:cid, 15, :t, '경상북도 봉화군 1', 'http://kto/f.jpg', 1) "
                "ON CONFLICT DO NOTHING"
            ),
            {"cid": cid, "t": f"축제-{cid}"},
        )
    await session.flush()


@pytest_asyncio.fixture
async def seeded_festivals(db_session: AsyncSession) -> None:
    await _seed(db_session)
    await _seed_festival_spots(db_session, [f"f{i}" for i in range(80)])


@pytest.mark.integration
async def test_festival_intent_returns_festival_cards_with_dday_tags(
    db_session, client, seeded_festivals, monkeypatch
) -> None:
    monkeypatch.setattr(
        ask_service.feed_services,
        "load_festival_pool",
        _festival_pool(
            [_festival_card("f1", title="봉화은어축제", region_label="경상북도 봉화군", dday="D-7")]
        ),
    )
    monkeypatch.setattr(
        intent_service, "extract_intent", _fake_intent(QueryIntent(festivalOnly=True))
    )
    _override_with_kto(db_session)
    try:
        res = await client.post("/v1/agent/ask", json={"question": "지금 열리는 축제"})
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    body = res.json()["data"]
    assert [s["contentId"] for s in body["spots"]] == ["f1"]
    assert body["spots"][0]["tag"] == "D-7"
    assert body["suggestions"] == []
    assert any(step["tool"] == "festival" for step in body["steps"])


@pytest.mark.integration
async def test_festival_region_hint_matches_raw_kto_address_vocabulary(
    db_session, client, seeded_festivals, monkeypatch
) -> None:
    monkeypatch.setattr(
        ask_service.feed_services,
        "load_festival_pool",
        _festival_pool(
            [
                _festival_card(
                    "f1",
                    title="여수밤바다불꽃축제",
                    region_label="전남광주통합특별시 여수시",
                    dday="D-3",
                ),
                _festival_card(
                    "f2", title="봉화은어축제", region_label="경상북도 봉화군", dday="D-7"
                ),
            ]
        ),
    )
    monkeypatch.setattr(
        intent_service,
        "extract_intent",
        _fake_intent(QueryIntent(festivalOnly=True, regionHints=["여수"])),
    )
    _override_with_kto(db_session)
    try:
        res = await client.post("/v1/agent/ask", json={"question": "여수 축제"})
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    body = res.json()["data"]
    assert [s["contentId"] for s in body["spots"]] == ["f1"]
    sentence = "".join(part["text"] for part in body["answer"])
    assert "전국에서 골랐어요" not in sentence


@pytest.mark.integration
async def test_festival_region_miss_falls_back_nationwide_and_says_so(
    db_session, client, seeded_festivals, monkeypatch
) -> None:
    monkeypatch.setattr(
        ask_service.feed_services,
        "load_festival_pool",
        _festival_pool(
            [_festival_card("f1", title="봉화은어축제", region_label="경상북도 봉화군", dday="D-7")]
        ),
    )
    monkeypatch.setattr(
        intent_service,
        "extract_intent",
        _fake_intent(QueryIntent(festivalOnly=True, regionHints=["제주"])),
    )
    _override_with_kto(db_session)
    try:
        res = await client.post("/v1/agent/ask", json={"question": "제주 축제"})
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    body = res.json()["data"]
    sentence = "".join(part["text"] for part in body["answer"])
    assert [s["contentId"] for s in body["spots"]] == ["f1"]
    assert sentence.startswith("봉화은어축제가 오늘 열려요.")
    assert "제주에는 오늘 열리는 축제가 없어 전국에서 골랐어요" in sentence


_FESTIVAL_TODAY = date(2026, 7, 12)


class _PagedFestivalKto:
    def __init__(self, items: list[dict]) -> None:
        self.items = items

    async def call(self, *args: object, **params: object) -> list[dict]:
        return self.items if params.get("pageNo") == 1 else []


def _running_festival_item(index: int) -> dict:
    return {
        "contentid": f"f{index}",
        "title": f"축제{index}",
        "addr1": "제주특별자치도 서귀포시 1" if index == 79 else "서울특별시 종로구 1",
        "firstimage": "https://kto/f.jpg",
        "eventstartdate": (_FESTIVAL_TODAY - timedelta(days=1)).strftime("%Y%m%d"),
        "eventenddate": (_FESTIVAL_TODAY + timedelta(days=index)).strftime("%Y%m%d"),
    }


@pytest.mark.integration
async def test_festival_in_region_beyond_the_channel_slice_is_still_found(
    db_session, client, seeded_festivals, monkeypatch
) -> None:
    monkeypatch.setattr(kto_channels, "_today", lambda: _FESTIVAL_TODAY)
    monkeypatch.setattr(
        intent_service,
        "extract_intent",
        _fake_intent(QueryIntent(festivalOnly=True, regionHints=["제주"])),
    )
    _override(db_session)
    app.dependency_overrides[get_kto] = lambda: _PagedFestivalKto(
        [_running_festival_item(i) for i in range(80)]
    )
    try:
        res = await client.post("/v1/agent/ask", json={"question": "제주 축제"})
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    body = res.json()["data"]
    sentence = "".join(part["text"] for part in body["answer"])
    assert [s["contentId"] for s in body["spots"]] == ["f79"]
    assert "전국에서 골랐어요" not in sentence


@pytest.mark.integration
async def test_festival_turn_echoes_only_the_axes_its_search_applied(
    db_session, client, seeded_festivals, monkeypatch
) -> None:
    monkeypatch.setattr(
        ask_service.feed_services,
        "load_festival_pool",
        _festival_pool(
            [_festival_card("f1", title="봉화은어축제", region_label="경상북도 봉화군", dday="D-7")]
        ),
    )
    monkeypatch.setattr(
        intent_service,
        "extract_intent",
        _fake_intent(
            QueryIntent(
                festivalOnly=True,
                regionHints=["봉화"],
                categoryKeywords=["계곡"],
                moodHints=["night"],
                crowdPreference="quiet",
                indoorOnly=True,
                nearMe=True,
            )
        ),
    )
    _override_with_kto(db_session)
    try:
        res = await client.post(
            "/v1/agent/ask",
            json={"question": "봉화 축제", "lat": LAT, "lng": LNG},
        )
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    echoed = res.json()["data"]["intent"]
    assert echoed["regionHints"] == ["봉화"]
    assert echoed["festivalOnly"] is True
    assert echoed["categoryKeywords"] == []
    assert echoed["moodHints"] == []
    assert echoed["crowdPreference"] == "any"
    assert echoed["indoorOnly"] is False
    assert echoed["nearMe"] is False


@pytest.mark.integration
async def test_festival_nationwide_fallback_stops_echoing_the_region_it_ignored(
    db_session, client, seeded_festivals, monkeypatch
) -> None:
    monkeypatch.setattr(
        ask_service.feed_services,
        "load_festival_pool",
        _festival_pool(
            [_festival_card("f1", title="봉화은어축제", region_label="경상북도 봉화군", dday="D-7")]
        ),
    )
    monkeypatch.setattr(
        intent_service,
        "extract_intent",
        _fake_intent(QueryIntent(festivalOnly=True, regionHints=["제주"])),
    )
    _override_with_kto(db_session)
    try:
        res = await client.post("/v1/agent/ask", json={"question": "제주 축제"})
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    data = res.json()["data"]
    assert [s["contentId"] for s in data["spots"]] == ["f1"]
    assert data["intent"]["regionHints"] == []


@pytest.mark.integration
async def test_festival_image_url_goes_through_the_copyright_display_helper(
    db_session, client, seeded_festivals, monkeypatch
) -> None:
    card = ChannelCardRow(
        content_id="f1",
        title="봉화은어축제",
        region_label="경상북도 봉화군",
        image_url="http://tong.visitkorea.or.kr/f.jpg",
        dday="D-7",
        cpyrht_div_cd="Type3",
    )
    monkeypatch.setattr(ask_service.feed_services, "load_festival_pool", _festival_pool([card]))
    monkeypatch.setattr(
        intent_service, "extract_intent", _fake_intent(QueryIntent(festivalOnly=True))
    )
    _override_with_kto(db_session)
    try:
        res = await client.post("/v1/agent/ask", json={"question": "축제"})
    finally:
        app.dependency_overrides.clear()

    body = res.json()["data"]
    assert body["spots"][0]["imageUrl"] == "https://tong.visitkorea.or.kr/f.jpg"


@pytest.mark.integration
async def test_festival_step_badge_counts_only_the_cards_that_ship(
    db_session, client, seeded_festivals, monkeypatch
) -> None:
    monkeypatch.setattr(
        ask_service.feed_services,
        "load_festival_pool",
        _festival_pool(
            [
                _festival_card(
                    f"f{i}", title=f"축제{i}", region_label="경상북도 봉화군", dday="D-7"
                )
                for i in range(3)
            ]
        ),
    )
    monkeypatch.setattr(
        intent_service, "extract_intent", _fake_intent(QueryIntent(festivalOnly=True))
    )
    monkeypatch.setattr(retrieve, "RESULT_LIMIT", 2)
    _override_with_kto(db_session)
    try:
        res = await client.post("/v1/agent/ask", json={"question": "축제"})
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    body = res.json()["data"]
    festival = next(step for step in body["steps"] if step["tool"] == "festival")
    assert festival["badge"] == "2곳"
    assert body["totalCount"] == len(body["spots"]) == 2


@pytest.mark.integration
async def test_festival_card_without_a_local_spot_row_is_dropped(
    db_session, client, seeded_festivals, monkeypatch
) -> None:
    monkeypatch.setattr(
        ask_service.feed_services,
        "load_festival_pool",
        _festival_pool(
            [
                _festival_card(
                    "unsynced", title="갓생긴축제", region_label="경상북도 봉화군", dday="D-1"
                ),
                _festival_card(
                    "f1", title="봉화은어축제", region_label="경상북도 봉화군", dday="D-7"
                ),
            ]
        ),
    )
    monkeypatch.setattr(
        intent_service, "extract_intent", _fake_intent(QueryIntent(festivalOnly=True))
    )
    _override_with_kto(db_session)
    try:
        res = await client.post("/v1/agent/ask", json={"question": "축제"})
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    body = res.json()["data"]
    assert [s["contentId"] for s in body["spots"]] == ["f1"]
    festival = next(step for step in body["steps"] if step["tool"] == "festival")
    assert festival["badge"] == "1곳"


@pytest.mark.integration
async def test_festival_turn_with_nothing_openable_reports_no_results(
    db_session, client, seeded_festivals, monkeypatch
) -> None:
    monkeypatch.setattr(
        ask_service.feed_services,
        "load_festival_pool",
        _festival_pool(
            [
                _festival_card(
                    "unsynced", title="갓생긴축제", region_label="경상북도 봉화군", dday="D-1"
                )
            ]
        ),
    )
    monkeypatch.setattr(
        intent_service, "extract_intent", _fake_intent(QueryIntent(festivalOnly=True))
    )
    _override_with_kto(db_session)
    try:
        res = await client.post("/v1/agent/ask", json={"question": "축제"})
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 422
    assert res.json()["error"]["code"] == "AGENT_NO_RESULTS"


@pytest.mark.integration
async def test_festival_in_region_that_is_not_synced_yet_does_not_claim_the_region_is_empty(
    db_session, client, seeded_festivals, monkeypatch
) -> None:
    monkeypatch.setattr(
        ask_service.feed_services,
        "load_festival_pool",
        _festival_pool(
            [
                _festival_card(
                    "unsynced",
                    title="서귀포신규축제",
                    region_label="제주특별자치도 서귀포시",
                    dday="D-1",
                ),
                _festival_card(
                    "f1", title="봉화은어축제", region_label="경상북도 봉화군", dday="D-7"
                ),
            ]
        ),
    )
    monkeypatch.setattr(
        intent_service,
        "extract_intent",
        _fake_intent(QueryIntent(festivalOnly=True, regionHints=["제주"])),
    )
    _override_with_kto(db_session)
    try:
        res = await client.post("/v1/agent/ask", json={"question": "제주 축제"})
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    body = res.json()["data"]
    assert [s["contentId"] for s in body["spots"]] == ["f1"]
    sentence = "".join(part["text"] for part in body["answer"])
    assert "제주 축제는 아직 상세 정보가 없어 전국에서 골랐어요" in sentence
    assert "제주에는 오늘 열리는 축제가 없어" not in sentence


@pytest.mark.integration
async def test_festival_multi_token_region_hint_matches_the_long_form_address(
    db_session, client, seeded_festivals, monkeypatch
) -> None:
    monkeypatch.setattr(
        ask_service.feed_services,
        "load_festival_pool",
        _festival_pool(
            [
                _festival_card(
                    "f1",
                    title="서귀포유채꽃축제",
                    region_label="제주특별자치도 서귀포시",
                    dday="D-3",
                ),
                _festival_card(
                    "f2", title="봉화은어축제", region_label="경상북도 봉화군", dday="D-7"
                ),
            ]
        ),
    )
    monkeypatch.setattr(
        intent_service,
        "extract_intent",
        _fake_intent(QueryIntent(festivalOnly=True, regionHints=["제주 서귀포"])),
    )
    _override_with_kto(db_session)
    try:
        res = await client.post("/v1/agent/ask", json={"question": "제주 서귀포 축제"})
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    body = res.json()["data"]
    assert [s["contentId"] for s in body["spots"]] == ["f1"]
    sentence = "".join(part["text"] for part in body["answer"])
    assert "전국에서 골랐어요" not in sentence


@pytest.mark.integration
async def test_festival_sido_alias_hint_matches_the_merged_address_vocabulary(
    db_session, client, seeded_festivals, monkeypatch
) -> None:
    monkeypatch.setattr(
        ask_service.feed_services,
        "load_festival_pool",
        _festival_pool(
            [
                _festival_card(
                    "f1",
                    title="여수밤바다불꽃축제",
                    region_label="전남광주통합특별시 여수시",
                    dday="D-3",
                ),
                _festival_card(
                    "f2", title="봉화은어축제", region_label="경상북도 봉화군", dday="D-7"
                ),
            ]
        ),
    )
    monkeypatch.setattr(
        intent_service,
        "extract_intent",
        _fake_intent(QueryIntent(festivalOnly=True, regionHints=["전라남도"])),
    )
    _override_with_kto(db_session)
    try:
        res = await client.post("/v1/agent/ask", json={"question": "전라남도 축제"})
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    body = res.json()["data"]
    assert [s["contentId"] for s in body["spots"]] == ["f1"]
    sentence = "".join(part["text"] for part in body["answer"])
    assert "전국에서 골랐어요" not in sentence


@pytest.mark.integration
async def test_festival_hint_buried_mid_token_still_falls_back_nationwide(
    db_session, client, seeded_festivals, monkeypatch
) -> None:
    monkeypatch.setattr(
        ask_service.feed_services,
        "load_festival_pool",
        _festival_pool(
            [
                _festival_card(
                    "f1",
                    title="여수밤바다불꽃축제",
                    region_label="전남광주통합특별시 여수시",
                    dday="D-3",
                )
            ]
        ),
    )
    monkeypatch.setattr(
        intent_service,
        "extract_intent",
        _fake_intent(QueryIntent(festivalOnly=True, regionHints=["광주"])),
    )
    _override_with_kto(db_session)
    try:
        res = await client.post("/v1/agent/ask", json={"question": "광주 축제"})
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    body = res.json()["data"]
    assert [s["contentId"] for s in body["spots"]] == ["f1"]
    sentence = "".join(part["text"] for part in body["answer"])
    assert "광주에는 오늘 열리는 축제가 없어 전국에서 골랐어요" in sentence


@pytest.mark.integration
async def test_a_dead_kto_answers_with_a_festival_code_not_a_gateway_error(
    db_session, client, seeded_festivals, monkeypatch
) -> None:
    async def down(redis: object, kto: object, **kwargs: object) -> list[ChannelCardRow]:
        raise KtoApiUnavailable()

    monkeypatch.setattr(ask_service.feed_services, "load_festival_pool", down)
    monkeypatch.setattr(
        intent_service, "extract_intent", _fake_intent(QueryIntent(festivalOnly=True))
    )
    _override_with_kto(db_session)
    try:
        res = await client.post("/v1/agent/ask", json={"question": "지금 열리는 축제"})
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 422
    assert res.json()["error"]["code"] == "AGENT_FESTIVAL_UNAVAILABLE"


@pytest.mark.integration
async def test_a_hanging_kto_does_not_hold_the_festival_turn_open(
    db_session, client, seeded_festivals, monkeypatch
) -> None:
    async def hang(redis: object, kto: object, **kwargs: object) -> list[ChannelCardRow]:
        raise TimeoutError()

    monkeypatch.setattr(ask_service.feed_services, "load_festival_pool", hang)
    monkeypatch.setattr(
        intent_service, "extract_intent", _fake_intent(QueryIntent(festivalOnly=True))
    )
    _override_with_kto(db_session)
    try:
        res = await client.post("/v1/agent/ask", json={"question": "지금 열리는 축제"})
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 422
    assert res.json()["error"]["code"] == "AGENT_FESTIVAL_UNAVAILABLE"


async def test_widening_names_the_sido_that_owns_the_narrowed_hint() -> None:
    session = _RegionSession(
        {
            "부산": [_RegionRow("부산광역시", None, 1)],
            "여수": [_RegionRow("전라남도", "여수시", 2)],
        }
    )

    scope = await retrieve.resolve_region_scope(session, hints=["부산", "여수"])

    assert scope.narrowed_hints == ("여수",)
    assert scope.narrowed_sidos == ("전라남도",)
    assert ask_service._widen_label(scope) == "여수 결과 없음 — 전라남도로 넓힘"


@pytest.mark.integration
async def test_a_photo_in_an_empty_sigungu_widens_instead_of_giving_up(
    db_session, client, seeded, monkeypatch
) -> None:
    for cid in ("v1", "j1"):
        await db_session.execute(
            text("INSERT INTO spot_embeddings (content_id, embedding) VALUES (:c, :v)"),
            {"c": cid, "v": _VEC},
        )
    await db_session.flush()

    tried: list[list[str]] = []
    real_match = photo_service.match_vector

    async def spy(session, vector, *, region_prefixes):  # type: ignore[no-untyped-def]
        tried.append(list(region_prefixes))
        return await real_match(session, vector, region_prefixes=region_prefixes)

    async def fake_intent(question: str) -> QueryIntent:
        return QueryIntent(regionHints=["수영"])

    async def fake_embed(*, image_bytes, image_mime):  # type: ignore[no-untyped-def]
        return [0.1] * 512

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    monkeypatch.setattr(photo_service, "embed_photo", fake_embed)
    monkeypatch.setattr(photo_service, "match_vector", spy)
    monkeypatch.setattr(ask_service.photo_service, "match_vector", spy)
    _override(db_session)
    try:
        res = await client.post(
            "/v1/agent/ask",
            files={"photo": ("a.jpg", b"x", "image/jpeg")},
            data={"question": "수영에서 이런 분위기"},
        )
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    assert tried == [["부산광역시 수영구"], ["부산광역시"]]
    answer = "".join(segment["text"] for segment in res.json()["data"]["answer"])
    assert "수영" in answer
    assert "부산광역시" in answer


async def test_two_narrowed_sigungus_both_appear_in_the_widening_notice() -> None:
    session = _RegionSession(
        {
            "경주": [_RegionRow("경상북도", "경주시", 2)],
            "여수": [_RegionRow("전라남도", "여수시", 2)],
        }
    )

    scope = await retrieve.resolve_region_scope(session, hints=["경주", "여수"])

    assert scope.narrowed_hints == ("경주", "여수")
    assert scope.narrowed_sidos == ("경상북도", "전라남도")
    assert ask_service._widen_label(scope) == "경주 · 여수 결과 없음 — 경상북도 · 전라남도로 넓힘"


@pytest.mark.integration
async def test_widening_hands_the_sido_back_so_follow_up_chips_do_not_renarrow(
    db_session, client, seeded, monkeypatch
) -> None:
    async def fake_intent(question: str) -> QueryIntent:
        return QueryIntent(categoryKeywords=["계곡"], regionHints=["수영"])

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    _override(db_session)
    try:
        res = await client.post("/v1/agent/ask", json={"question": "수영 계곡"})
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    assert res.json()["data"]["intent"]["regionHints"] == ["부산광역시"]


@pytest.mark.integration
async def test_a_sigungu_whose_only_match_lacks_coords_still_widens_for_near_me(
    db_session, client, seeded, monkeypatch
) -> None:
    await db_session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, addr1, first_image_url, "
            "show_flag, lcls_systm1, lcls_systm3, ldong_regn_cd, ldong_signgu_cd) "
            "VALUES ('n1', 12, '수영계곡', '부산광역시 수영구 1', 'http://kto/i.jpg', 1, "
            "'NA', 'NA010100', '26', '26500')"
        )
    )
    await db_session.flush()

    async def fake_intent(question: str) -> QueryIntent:
        return QueryIntent(categoryKeywords=["계곡"], regionHints=["수영"], nearMe=True)

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    _override(db_session)
    try:
        res = await client.post(
            "/v1/agent/ask", json={"question": "수영 계곡", "lat": LAT, "lng": LNG}
        )
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    data = res.json()["data"]
    assert {spot["contentId"] for spot in data["spots"]} == {"v1", "v2", "v3"}
    assert any("넓힘" in step["label"] for step in data["steps"])


def test_indoor_chip_is_withheld_when_no_result_is_indoor() -> None:
    chips = suggest_service.derive(
        QueryIntent(), has_coords=False, result_count=20, indoor_available=False
    )

    assert "실내만" not in [chip.label for chip in chips]


def test_indoor_chip_is_offered_when_some_result_is_indoor() -> None:
    chips = suggest_service.derive(
        QueryIntent(), has_coords=False, result_count=20, indoor_available=True
    )

    assert "실내만" in [chip.label for chip in chips]


@pytest.mark.integration
async def test_a_festival_with_crowd_data_keeps_the_crowd_chip(
    db_session, client, seeded_festivals, monkeypatch
) -> None:
    await db_session.execute(
        text(
            "INSERT INTO spot_concentration (content_id, concentration_rate, base_ymd, raw_name) "
            "VALUES ('f1', 55.00, DATE '2026-07-01', 'f1') ON CONFLICT DO NOTHING"
        )
    )
    await db_session.flush()
    monkeypatch.setattr(
        ask_service.feed_services,
        "load_festival_pool",
        _festival_pool(
            [
                _festival_card("f1", title="봉화축제", region_label="경상북도 봉화군", dday="D-2"),
                _festival_card("f2", title="영주축제", region_label="경상북도 영주시", dday="D-5"),
            ]
        ),
    )
    monkeypatch.setattr(
        intent_service, "extract_intent", _fake_intent(QueryIntent(festivalOnly=True))
    )
    _override_with_kto(db_session)
    try:
        res = await client.post("/v1/agent/ask", json={"question": "지금 열리는 축제"})
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    crowd = {spot["contentId"]: spot["hasCrowd"] for spot in res.json()["data"]["spots"]}
    assert crowd["f1"] is True
    assert crowd["f2"] is False


@pytest.mark.integration
async def test_a_festival_without_a_local_image_still_reports_its_crowd_data(
    db_session, client, seeded_festivals, monkeypatch
) -> None:
    await db_session.execute(
        text("UPDATE spots SET first_image_url = NULL WHERE content_id = 'f1'")
    )
    await db_session.execute(
        text(
            "INSERT INTO spot_concentration (content_id, concentration_rate, base_ymd, raw_name) "
            "VALUES ('f1', 55.00, DATE '2026-07-01', 'f1') ON CONFLICT DO NOTHING"
        )
    )
    await db_session.flush()
    monkeypatch.setattr(
        ask_service.feed_services,
        "load_festival_pool",
        _festival_pool(
            [_festival_card("f1", title="봉화축제", region_label="경상북도 봉화군", dday="D-2")]
        ),
    )
    monkeypatch.setattr(
        intent_service, "extract_intent", _fake_intent(QueryIntent(festivalOnly=True))
    )
    _override_with_kto(db_session)
    try:
        res = await client.post("/v1/agent/ask", json={"question": "지금 열리는 축제"})
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    assert res.json()["data"]["spots"][0]["hasCrowd"] is True


def test_a_truncated_candidate_sweep_does_not_hide_the_indoor_chip() -> None:
    chips = suggest_service.derive(
        QueryIntent(), has_coords=False, result_count=20, indoor_available=True
    )

    assert "실내만" in [chip.label for chip in chips]


def test_zero_chips_only_ever_offer_to_widen_the_region() -> None:
    intent = QueryIntent(
        categoryKeywords=["계곡"], regionHints=["제주"], indoorOnly=True, crowdPreference="quiet"
    )

    chips = suggest_service.derive_for_zero(intent, has_coords=False)

    assert [chip.label for chip in chips] == ["지역 넓히기"]
    assert [chip.patch.drop for chip in chips] == ["region"]


def test_zero_chips_are_empty_without_a_region_to_widen() -> None:
    assert suggest_service.derive_for_zero(QueryIntent(), has_coords=False) == []
    assert (
        suggest_service.derive_for_zero(
            QueryIntent(categoryKeywords=["계곡"], indoorOnly=True, nearMe=True), has_coords=True
        )
        == []
    )


def test_zero_chips_skip_region_when_the_hint_never_resolved() -> None:
    intent = QueryIntent(categoryKeywords=["계곡"], regionHints=["없는지역"])

    unresolved = suggest_service.derive_for_zero(
        ask_service.searched_intent(
            intent, has_coords=False, region_hints=[], keywords=list(intent.categoryKeywords)
        ),
        has_coords=False,
    )
    resolved = suggest_service.derive_for_zero(intent, has_coords=False)

    assert unresolved == []
    assert [chip.label for chip in resolved] == ["지역 넓히기"]


@pytest.mark.integration
async def test_a_zero_turn_does_not_claim_a_near_condition_it_never_applied(
    db_session, client, seeded, monkeypatch
) -> None:
    async def fake_intent(question: str) -> QueryIntent:
        return QueryIntent(categoryKeywords=["존재하지않는유형"], nearMe=True)

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    _override(db_session)
    try:
        res = await client.post("/v1/agent/ask", json={"question": "근처 존재하지않는유형"})
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    data = res.json()["data"]
    assert data["spots"] == []
    answer = "".join(segment["text"] for segment in data["answer"])
    assert "내 근처" not in answer
    assert "내 근처 조건 풀기" not in [chip["label"] for chip in data["refinements"]]


@pytest.mark.integration
async def test_a_zero_turn_does_not_claim_a_region_the_search_never_used(
    db_session, client, seeded, monkeypatch
) -> None:
    async def fake_intent(question: str) -> QueryIntent:
        return QueryIntent(categoryKeywords=["존재하지않는유형"], regionHints=["없는지역이름"])

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    _override(db_session)
    try:
        res = await client.post("/v1/agent/ask", json={"question": "없는지역이름 존재하지않는유형"})
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    data = res.json()["data"]
    assert data["spots"] == []
    answer = "".join(segment["text"] for segment in data["answer"])
    assert "없는지역이름" not in answer
    assert "지역 넓히기" not in [chip["label"] for chip in data["refinements"]]


@pytest.mark.integration
async def test_a_zero_photo_turn_lists_only_the_axes_the_photo_search_applies(
    db_session, client, seeded, monkeypatch
) -> None:
    async def fake_intent(question: str) -> QueryIntent:
        return QueryIntent(
            categoryKeywords=["박물관"],
            indoorOnly=True,
            crowdPreference="quiet",
            regionHints=["제주"],
        )

    async def fake_embed(*, image_bytes, image_mime):
        return [0.1] * 512

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    monkeypatch.setattr(photo_service, "embed_photo", fake_embed)
    _override(db_session)
    try:
        res = await client.post(
            "/v1/agent/ask",
            files={"photo": ("a.jpg", b"x", "image/jpeg")},
            data={"question": "제주 실내 박물관처럼"},
        )
    finally:
        app.dependency_overrides.clear()

    answer = "".join(segment["text"] for segment in res.json()["data"]["answer"])
    assert "제주" in answer
    assert "박물관" not in answer
    assert "실내" not in answer
    assert "한적" not in answer


@pytest.mark.integration
async def test_a_zero_photo_turn_blames_the_vector_match_not_the_distance_sort(
    db_session, client, seeded, monkeypatch
) -> None:
    async def fake_intent(question: str) -> QueryIntent:
        return QueryIntent(regionHints=["제주"], nearMe=True)

    async def fake_embed(*, image_bytes, image_mime):
        return [0.1] * 512

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    monkeypatch.setattr(photo_service, "embed_photo", fake_embed)
    _override(db_session)
    try:
        res = await client.post(
            "/v1/agent/ask",
            files={"photo": ("a.jpg", b"x", "image/jpeg")},
            data={"question": "제주 근처 이런 분위기", "lat": str(LAT), "lng": str(LNG)},
        )
    finally:
        app.dependency_overrides.clear()

    steps = res.json()["data"]["steps"]
    photo_steps = [step for step in steps if step["tool"] == "photo_match"]
    assert photo_steps[-1]["badge"] == "0곳"


def test_zero_chips_do_not_offer_a_drop_that_lands_on_a_named_place_alone() -> None:
    intent = QueryIntent(
        categoryKeywords=["계곡"],
        regionHints=["없는지역"],
        namedPlaces=[ExtractedPlace(name="어떤장소", nameKo="어떤장소")],
    )

    unresolved = suggest_service.derive_for_zero(
        ask_service.searched_intent(
            intent, has_coords=False, region_hints=[], keywords=list(intent.categoryKeywords)
        ),
        has_coords=False,
    )

    assert [chip.label for chip in unresolved] == []


@pytest.mark.integration
async def test_an_old_app_keeps_the_error_instead_of_a_turn_it_cannot_escape(
    db_session, client, seeded, monkeypatch
) -> None:
    async def fake_intent(question: str) -> QueryIntent:
        return QueryIntent(categoryKeywords=["존재하지않는유형"])

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    _override(db_session)
    try:
        res = await client.post(
            "/v1/agent/ask", json={"question": "존재하지않는유형", "region": "jeju"}
        )
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 422
    assert res.json()["error"]["code"] == "AGENT_NO_RESULTS"


@pytest.mark.integration
async def test_an_old_app_gets_back_the_region_its_search_actually_used(
    db_session, client, seeded, monkeypatch
) -> None:
    async def fake_intent(question: str) -> QueryIntent:
        return QueryIntent(categoryKeywords=["계곡"])

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    _override(db_session)
    try:
        res = await client.post("/v1/agent/ask", json={"question": "계곡", "region": "jeju"})
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    assert res.json()["data"]["intent"]["regionHints"] == ["제주"]


@pytest.mark.integration
async def test_a_photo_with_no_releasable_axis_stays_an_error_not_an_empty_turn(
    db_session, client, seeded, monkeypatch
) -> None:
    async def fake_embed(*, image_bytes, image_mime):
        return [0.1] * 512

    monkeypatch.setattr(photo_service, "embed_photo", fake_embed)
    _override(db_session)
    try:
        res = await client.post("/v1/agent/ask", files={"photo": ("a.jpg", b"x", "image/jpeg")})
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 422
    assert res.json()["error"]["code"] == "AGENT_NO_RESULTS"


@pytest.mark.integration
async def test_an_old_app_on_the_default_region_is_still_treated_as_legacy(
    db_session, client, seeded, monkeypatch
) -> None:
    async def fake_intent(question: str) -> QueryIntent:
        return QueryIntent(categoryKeywords=["존재하지않는유형"])

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    _override(db_session)
    try:
        res = await client.post(
            "/v1/agent/ask", json={"question": "존재하지않는유형", "region": "all"}
        )
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 422
    assert res.json()["error"]["code"] == "AGENT_NO_RESULTS"


@pytest.mark.integration
async def test_a_mood_only_zero_turn_names_the_mood_instead_of_saying_this_condition(
    db_session, client, seeded, monkeypatch
) -> None:
    async def fake_intent(question: str) -> QueryIntent:
        return QueryIntent(moodHints=["lake"], crowdPreference="quiet")

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    _override(db_session)
    try:
        res = await client.post("/v1/agent/ask", json={"question": "한적한 호수"})
    finally:
        app.dependency_overrides.clear()

    data = res.json()["data"]
    assert data["spots"] == []
    answer = "".join(segment["text"] for segment in data["answer"])
    assert answer.startswith("분위기 + 한적 조건으로는 ")
    assert "이 조건 조건" not in answer


def test_zero_answer_drops_a_category_that_never_reached_the_query() -> None:
    intent = QueryIntent(categoryKeywords=["존재하지않는유형"], indoorOnly=True)

    unapplied = ask_service._applied_conditions(
        ask_service.searched_intent(
            intent, has_coords=False, region_hints=list(intent.regionHints), keywords=[]
        ),
        axes=suggest_service.ALL_AXES,
    )
    applied = ask_service._applied_conditions(intent, axes=suggest_service.ALL_AXES)

    assert unapplied == ["실내"]
    assert applied == ["존재하지않는유형", "실내"]


def test_a_mood_that_survives_an_unresolved_keyword_is_labeled_as_mood() -> None:
    intent = QueryIntent(categoryKeywords=["없는유형"], moodHints=["sea"])

    searched = ask_service.searched_intent(
        intent, has_coords=False, region_hints=list(intent.regionHints), keywords=[]
    )

    assert ask_service._applied_conditions(searched, axes=suggest_service.ALL_AXES) == ["분위기"]


def test_searched_intent_leaves_an_intent_alone_when_every_axis_reached_the_query() -> None:
    intent = QueryIntent(categoryKeywords=["계곡"], regionHints=["제주"], nearMe=True)

    assert (
        ask_service.searched_intent(
            intent,
            has_coords=True,
            region_hints=list(intent.regionHints),
            keywords=list(intent.categoryKeywords),
        )
        is intent
    )


@pytest.mark.integration
async def test_a_zero_turn_hands_back_an_intent_the_drop_chip_can_actually_move(
    db_session, client, seeded, monkeypatch
) -> None:
    async def fake_intent(question: str) -> QueryIntent:
        return QueryIntent(categoryKeywords=["존재하지않는유형"], regionHints=["없는지역이름"])

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    _override(db_session)
    try:
        res = await client.post("/v1/agent/ask", json={"question": "없는지역이름 존재하지않는유형"})
    finally:
        app.dependency_overrides.clear()

    data = res.json()["data"]
    assert data["spots"] == []
    assert data["intent"]["regionHints"] == []


@pytest.mark.integration
async def test_a_zero_turn_keeps_only_the_region_hint_that_actually_resolved(
    db_session, client, seeded, monkeypatch
) -> None:
    async def fake_intent(question: str) -> QueryIntent:
        return QueryIntent(
            categoryKeywords=["존재하지않는유형"], regionHints=["없는지역이름", "제주"]
        )

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    _override(db_session)
    try:
        res = await client.post("/v1/agent/ask", json={"question": "없는지역이름 제주"})
    finally:
        app.dependency_overrides.clear()

    data = res.json()["data"]
    assert data["spots"] == []
    answer = "".join(segment["text"] for segment in data["answer"])
    assert "없는지역이름" not in answer
    assert "없는지역이름" not in data["intent"]["regionHints"]


def test_searched_intent_keeps_only_the_values_that_reached_the_query() -> None:
    intent = QueryIntent(
        categoryKeywords=["박물관", "없는유형"], regionHints=["없는지역", "제주"], nearMe=True
    )

    searched = ask_service.searched_intent(
        intent, has_coords=False, region_hints=["제주특별자치도"], keywords=["박물관"]
    )

    assert searched.regionHints == ["제주특별자치도"]
    assert searched.categoryKeywords == ["박물관"]
    assert searched.nearMe is False


@pytest.mark.integration
async def test_a_photo_that_matched_nothing_does_not_blame_the_near_filter(
    db_session, client, seeded, monkeypatch
) -> None:
    async def fake_intent(question: str) -> QueryIntent:
        return QueryIntent(regionHints=["제주"], nearMe=True)

    async def fake_embed(*, image_bytes, image_mime):
        return [0.1] * 512

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    monkeypatch.setattr(photo_service, "embed_photo", fake_embed)
    _override(db_session)
    try:
        res = await client.post(
            "/v1/agent/ask",
            files={"photo": ("a.jpg", b"x", "image/jpeg")},
            data={"question": "제주 근처 이런 분위기", "lat": str(LAT), "lng": str(LNG)},
        )
    finally:
        app.dependency_overrides.clear()

    data = res.json()["data"]
    labels = [chip["label"] for chip in data["refinements"]]
    assert "내 근처 조건 풀기" not in labels
    assert "내 근처" not in "".join(segment["text"] for segment in data["answer"])


@pytest.mark.integration
async def test_a_title_search_that_found_nothing_does_not_blame_the_near_filter(
    db_session, client, seeded, monkeypatch
) -> None:
    async def fake_intent(question: str) -> QueryIntent:
        return QueryIntent(categoryKeywords=["존재하지않는유형"], nearMe=True)

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    _override(db_session)
    try:
        res = await client.post(
            "/v1/agent/ask",
            json={"question": "근처 존재하지않는유형", "lat": LAT, "lng": LNG},
        )
    finally:
        app.dependency_overrides.clear()

    data = res.json()["data"]
    assert data["spots"] == []
    assert "내 근처 조건 풀기" not in [chip["label"] for chip in data["refinements"]]
    assert "내 근처" not in "".join(segment["text"] for segment in data["answer"])


@pytest.mark.integration
async def test_a_category_search_emptied_by_the_near_clause_names_it_as_the_culprit(
    db_session, client, seeded, monkeypatch
) -> None:
    await db_session.execute(text("UPDATE spots SET mapx = NULL, mapy = NULL"))
    await db_session.flush()

    async def fake_intent(question: str) -> QueryIntent:
        return QueryIntent(categoryKeywords=["계곡"], nearMe=True)

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    _override(db_session)
    try:
        res = await client.post(
            "/v1/agent/ask", json={"question": "근처 계곡", "lat": LAT, "lng": LNG}
        )
    finally:
        app.dependency_overrides.clear()

    data = res.json()["data"]
    assert data["spots"] == []
    assert "내 근처" in "".join(segment["text"] for segment in data["answer"])


@pytest.mark.integration
async def test_a_category_with_no_rows_at_all_does_not_blame_the_near_filter(
    db_session, client, seeded, monkeypatch
) -> None:
    async def fake_intent(question: str) -> QueryIntent:
        return QueryIntent(categoryKeywords=["박물관"], regionHints=["제주"], nearMe=True)

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    _override(db_session)
    try:
        res = await client.post(
            "/v1/agent/ask", json={"question": "제주 근처 박물관", "lat": LAT, "lng": LNG}
        )
    finally:
        app.dependency_overrides.clear()

    data = res.json()["data"]
    assert data["spots"] == []
    assert "내 근처 조건 풀기" not in [chip["label"] for chip in data["refinements"]]


@pytest.mark.integration
async def test_a_photo_that_matched_nothing_leaves_one_culprit_in_the_funnel(
    db_session, client, seeded, monkeypatch
) -> None:
    async def fake_intent(question: str) -> QueryIntent:
        return QueryIntent(regionHints=["제주"], nearMe=True)

    async def fake_embed(*, image_bytes, image_mime):
        return [0.1] * 512

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    monkeypatch.setattr(photo_service, "embed_photo", fake_embed)
    _override(db_session)
    try:
        res = await client.post(
            "/v1/agent/ask",
            files={"photo": ("a.jpg", b"x", "image/jpeg")},
            data={"question": "제주 근처 이런 분위기", "lat": str(LAT), "lng": str(LNG)},
        )
    finally:
        app.dependency_overrides.clear()

    steps = res.json()["data"]["steps"]
    assert [step["tool"] for step in steps if step["tool"] == "nearby"] == []
    assert len([step for step in steps if step["badge"] == "0곳"]) == 1


@pytest.mark.integration
async def test_a_near_only_zero_leaves_one_culprit_and_shows_what_releasing_gives(
    db_session, client, seeded, monkeypatch
) -> None:
    await db_session.execute(text("UPDATE spots SET mapx = NULL, mapy = NULL"))
    await db_session.flush()

    async def fake_intent(question: str) -> QueryIntent:
        return QueryIntent(categoryKeywords=["계곡"], nearMe=True)

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    _override(db_session)
    try:
        res = await client.post(
            "/v1/agent/ask", json={"question": "근처 계곡", "lat": LAT, "lng": LNG}
        )
    finally:
        app.dependency_overrides.clear()

    data = res.json()["data"]
    assert data["spots"] == []
    assert len([step for step in data["steps"] if step["badge"] == "0곳"]) == 1
    probe = [step for step in data["steps"] if step["label"] == ask_service.NEAR_PROBE_LABEL]
    assert probe and probe[0]["badge"] != "0곳"
    assert "내 근처" in "".join(segment["text"] for segment in data["answer"])


@pytest.mark.integration
async def test_the_near_probe_reuses_the_codes_the_indoor_fallback_settled_on(
    db_session, client, seeded, monkeypatch
) -> None:
    await db_session.execute(text("UPDATE spots SET mapx = NULL, mapy = NULL"))
    await db_session.flush()

    seen: list[list[str]] = []
    real_search = retrieve.search_candidates

    async def spy(session, **kwargs):  # type: ignore[no-untyped-def]
        seen.append(list(kwargs["codes"]))
        return await real_search(session, **kwargs)

    monkeypatch.setattr(retrieve, "search_candidates", spy)

    async def fake_intent(question: str) -> QueryIntent:
        return QueryIntent(categoryKeywords=["계곡"], indoorOnly=True, nearMe=True)

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    _override(db_session)
    try:
        await client.post(
            "/v1/agent/ask", json={"question": "근처 실내 계곡", "lat": LAT, "lng": LNG}
        )
    finally:
        app.dependency_overrides.clear()

    assert seen[-1] == seen[-2] == []


@pytest.mark.integration
async def test_a_mood_step_that_filtered_nothing_is_not_a_second_culprit(
    db_session, client, seeded, monkeypatch
) -> None:
    async def fake_intent(question: str) -> QueryIntent:
        return QueryIntent(moodHints=["lake"], crowdPreference="quiet")

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    _override(db_session)
    try:
        res = await client.post("/v1/agent/ask", json={"question": "한적한 호수"})
    finally:
        app.dependency_overrides.clear()

    data = res.json()["data"]
    assert data["spots"] == []
    assert [step["tool"] for step in data["steps"] if step["tool"] == "mood_search"] == []
    assert len([step for step in data["steps"] if step["badge"] == "0곳"]) == 1


@pytest.mark.integration
async def test_a_crowd_tagged_answer_says_which_day_the_prediction_is_from(
    db_session, client, seeded, monkeypatch
) -> None:
    async def fake_intent(question: str) -> QueryIntent:
        return QueryIntent(categoryKeywords=["계곡"], crowdPreference="quiet")

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    _override(db_session)
    try:
        res = await client.post("/v1/agent/ask", json={"question": "한적한 계곡"})
    finally:
        app.dependency_overrides.clear()

    basis = res.json()["data"]["tagBasis"]
    assert basis is not None
    assert basis.startswith("혼잡도 ")
    assert basis.endswith("예측 기준")


@pytest.mark.integration
async def test_a_distance_tagged_answer_says_the_distance_is_straight_line(
    db_session, client, seeded, monkeypatch
) -> None:
    async def fake_intent(question: str) -> QueryIntent:
        return QueryIntent(categoryKeywords=["계곡"], nearMe=True)

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    _override(db_session)
    try:
        res = await client.post(
            "/v1/agent/ask", json={"question": "근처 계곡", "lat": LAT, "lng": LNG}
        )
    finally:
        app.dependency_overrides.clear()

    assert res.json()["data"]["tagBasis"] == "직선거리 기준"


@pytest.mark.integration
async def test_a_basis_line_never_names_the_agency_that_lives_on_the_legal_page(
    db_session, client, seeded, monkeypatch
) -> None:
    async def fake_intent(question: str) -> QueryIntent:
        return QueryIntent(categoryKeywords=["계곡"], crowdPreference="quiet")

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    _override(db_session)
    try:
        res = await client.post("/v1/agent/ask", json={"question": "한적한 계곡"})
    finally:
        app.dependency_overrides.clear()

    assert "한국관광공사" not in (res.json()["data"]["tagBasis"] or "")


@pytest.mark.integration
async def test_loading_candidates_by_id_carries_the_crowd_base_day(db_session, seeded) -> None:
    rows = await repositories.load_candidates_by_ids(db_session, ["v1"])

    assert rows["v1"].base_ymd is not None


def test_a_mixed_crowd_batch_does_not_claim_a_single_day() -> None:
    from dataclasses import replace
    from datetime import date

    rows = [
        replace(_row("a", rate=10.0), base_ymd=date(2026, 8, 3)),
        replace(_row("b", rate=20.0), base_ymd=date(2026, 7, 20)),
    ]

    assert ask_service._crowd_basis(rows) == "혼잡도 예측 기준"


def test_one_shared_day_is_named_outright() -> None:
    from dataclasses import replace
    from datetime import date

    rows = [
        replace(_row("a", rate=10.0), base_ymd=date(2026, 8, 3)),
        replace(_row("b", rate=20.0), base_ymd=date(2026, 8, 3)),
    ]

    assert ask_service._crowd_basis(rows) == "혼잡도 8/3 예측 기준"


def test_a_mixed_tag_batch_does_not_claim_every_card_is_a_distance() -> None:
    from dataclasses import replace
    from datetime import date

    rows = [replace(_row("a", rate=10.0), base_ymd=date(2026, 8, 3))]
    mixed = [
        AgentSpotCard(contentId="a", title="t", regionLabel="r", tag="3.2km"),
        AgentSpotCard(contentId="b", title="t", regionLabel="r", tag="한산"),
    ]

    assert ask_service._tag_basis(rows, mixed, near=True) == "혼잡도 8/3 예측 기준"


def test_an_all_distance_batch_says_so() -> None:
    cards = [
        AgentSpotCard(contentId="a", title="t", regionLabel="r", tag="3.2km"),
        AgentSpotCard(contentId="b", title="t", regionLabel="r", tag="0.4km"),
    ]

    assert ask_service._tag_basis([], cards, near=True) == "직선거리 기준"


def test_a_metre_tagged_batch_keeps_the_straight_line_basis() -> None:
    cards = [
        AgentSpotCard(contentId="a", title="t", regionLabel="r", tag="870m"),
        AgentSpotCard(contentId="b", title="t", regionLabel="r", tag="40m"),
    ]

    assert ask_service._tag_basis([], cards, near=True) == "직선거리 기준"


def test_metres_and_kilometres_mixed_still_read_as_one_distance_batch() -> None:
    cards = [
        AgentSpotCard(contentId="a", title="t", regionLabel="r", tag="870m"),
        AgentSpotCard(contentId="b", title="t", regionLabel="r", tag="3.2km"),
    ]

    assert ask_service._tag_basis([], cards, near=True) == "직선거리 기준"


@pytest.mark.parametrize("tag", ["40m", "870m", "1.0km", "3.2km", "12km"])
def test_every_distance_label_the_formatter_emits_is_shaped_like_a_distance(tag) -> None:
    assert ask_service._is_distance_tag(tag)


@pytest.mark.parametrize("tag", ["한산", "하위 8%", "유사도 87%", "D-3", "바다뷰", None, ""])
def test_a_non_distance_tag_is_not_mistaken_for_one(tag) -> None:
    assert not ask_service._is_distance_tag(tag)


def test_the_formatter_and_the_basis_gate_agree_on_every_step_from_zero_to_two_km() -> None:
    labels = [ask_service._meters_label(float(m)) for m in range(0, 2000, 7)]

    assert all(ask_service._is_distance_tag(label) for label in labels)


def test_no_crowd_tag_means_no_crowd_basis() -> None:
    from dataclasses import replace
    from datetime import date

    rows = [replace(_row("a", rate=10.0), base_ymd=date(2026, 8, 3))]
    cards = [
        AgentSpotCard(contentId="a", title="t", regionLabel="r", tag=None),
        AgentSpotCard(contentId="b", title="t", regionLabel="r", tag="3.2km"),
    ]

    assert ask_service._tag_basis(rows, cards, near=True) is None


def test_a_visible_crowd_tag_brings_the_crowd_basis_back() -> None:
    from dataclasses import replace
    from datetime import date

    rows = [replace(_row("a", rate=10.0), base_ymd=date(2026, 8, 3))]
    cards = [
        AgentSpotCard(contentId="a", title="t", regionLabel="r", tag="하위 8%"),
        AgentSpotCard(contentId="b", title="t", regionLabel="r", tag="3.2km"),
    ]

    assert ask_service._tag_basis(rows, cards, near=True) == "혼잡도 8/3 예측 기준"


def test_a_card_carries_the_category_the_map_pin_draws() -> None:
    from dataclasses import replace

    card = retrieve.to_card(replace(_row("a", rate=None), category_group="cafe"), tag=None)

    assert card.categoryGroup == "cafe"


def test_a_card_with_no_derivable_category_leaves_the_pin_generic() -> None:
    assert retrieve.to_card(_row("a", rate=None), tag=None).categoryGroup is None


def test_an_indoor_venue_in_the_travel_pool_still_gets_a_pin_category() -> None:
    assert repositories.category_group("VE", "VE06", None) == "attraction"


def test_category_group_defers_to_the_shared_mapping_for_food_codes() -> None:
    assert repositories.category_group("FD", "FD05", "FD050100") == "cafe"


def test_category_group_leaves_an_unknown_branch_generic() -> None:
    assert repositories.category_group("XX", None, None) is None


class _ExplodingSession:
    async def execute(self, *args: object, **kwargs: object) -> object:
        raise AssertionError("a question with no condition must not reach the database")


async def _ask_blank(*, legacy_client: bool = False) -> AskResponse:
    return await ask_service.ask(
        _ExplodingSession(),  # type: ignore[arg-type]
        FakeRedis(),
        None,
        question="안녕",
        lat=None,
        lng=None,
        image_bytes=None,
        image_mime=None,
        intent=QueryIntent(),
        legacy_client=legacy_client,
    )


async def test_a_question_with_no_condition_never_searches() -> None:
    answer = await _ask_blank()

    assert answer.totalCount == 0
    assert answer.spots == []


async def test_a_typed_question_with_no_condition_asks_for_a_region() -> None:
    answer = await _ask_blank()

    assert "".join(segment.text for segment in answer.answer) == ask_service.NO_AXIS_ANSWER


async def test_a_legacy_client_gets_an_error_instead_of_a_blank_turn() -> None:
    with pytest.raises(AgentNoResults):
        await _ask_blank(legacy_client=True)


def test_a_single_axis_is_enough_to_search() -> None:
    assert not ask_service._asks_for_nothing(QueryIntent(nearMe=True), prefixes=[])


def test_a_crowd_preference_alone_is_enough_to_search() -> None:
    assert not ask_service._asks_for_nothing(QueryIntent(crowdPreference="quiet"), prefixes=[])


def test_a_pre_ota_region_alone_is_enough_to_search() -> None:
    assert not ask_service._asks_for_nothing(QueryIntent(), prefixes=["제주"])


def test_a_similarity_only_batch_names_the_photo_comparison_not_the_crowd() -> None:
    from dataclasses import replace
    from datetime import date

    rows = [replace(_row("a", rate=10.0), base_ymd=date(2026, 8, 3))]
    cards = [AgentSpotCard(contentId="a", title="t", regionLabel="r", tag="유사도 84%")]

    assert ask_service._tag_basis(rows, cards, near=False) == ask_service.PHOTO_BASIS


@pytest.mark.integration
async def test_a_follow_up_hands_the_previous_turn_to_the_extractor(
    db_session, client, seeded, monkeypatch
) -> None:
    seen: dict[str, object] = {}

    async def fake_intent(question, *, prior=None, prior_spots=None):  # type: ignore[no-untyped-def]
        seen["prior"] = prior
        seen["spots"] = prior_spots
        return QueryIntent(categoryKeywords=["계곡"], regionHints=["제주"])

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    _override(db_session)
    try:
        await client.post(
            "/v1/agent/ask",
            json={
                "question": "거기 근처 카페는?",
                "context": {
                    "intent": {"categoryKeywords": ["해수욕장"], "regionHints": ["제주"]},
                    "spots": [{"contentId": "v1", "title": "하고수동해수욕장"}],
                },
            },
        )
    finally:
        app.dependency_overrides.clear()

    prior = seen["prior"]
    assert prior is not None and prior.categoryKeywords == ["해수욕장"]
    assert seen["spots"] == ["하고수동해수욕장"]


@pytest.mark.integration
async def test_a_first_question_reaches_the_extractor_without_context(
    db_session, client, seeded, monkeypatch
) -> None:
    async def fake_intent(question: str) -> QueryIntent:
        return QueryIntent(categoryKeywords=["계곡"])

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    _override(db_session)
    try:
        res = await client.post("/v1/agent/ask", json={"question": "계곡"})
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    labels = [step["label"] for step in res.json()["data"]["steps"]]
    assert ask_service.CONTEXT_INTENT_LABEL not in labels


@pytest.mark.integration
async def test_a_context_carrying_turn_says_so_in_the_funnel(
    db_session, client, seeded, monkeypatch
) -> None:
    async def fake_intent(question, *, prior=None, prior_spots=None):  # type: ignore[no-untyped-def]
        return QueryIntent(categoryKeywords=["계곡"])

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    _override(db_session)
    try:
        res = await client.post(
            "/v1/agent/ask",
            json={
                "question": "더 한적한 곳",
                "context": {"spots": [{"contentId": "v1", "title": "무릉계곡"}]},
            },
        )
    finally:
        app.dependency_overrides.clear()

    labels = [step["label"] for step in res.json()["data"]["steps"]]
    assert ask_service.CONTEXT_INTENT_LABEL in labels


@pytest.mark.integration
async def test_a_prepared_intent_still_skips_the_extractor_even_with_context(
    db_session, client, seeded, monkeypatch
) -> None:
    async def boom(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("extractor must not run when intent is prepared")

    monkeypatch.setattr(intent_service, "extract_intent", boom)
    _override(db_session)
    try:
        res = await client.post(
            "/v1/agent/ask",
            json={
                "intent": {"categoryKeywords": ["계곡"], "regionHints": []},
                "context": {"spots": [{"contentId": "v1", "title": "무릉계곡"}]},
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200


def test_a_zero_answer_leads_with_the_conditions_that_failed() -> None:
    segments = ask_service._zero_answer(
        QueryIntent(regionHints=["울릉도"], indoorOnly=True),
        axes=suggest_service.ALL_AXES,
    )

    text = "".join(s.text for s in segments)
    assert text.startswith("울릉도 + 실내 조건으로는 없어요.")
    assert "지역을 넓히면" in text
    assert [s.text for s in segments if s.emphasis] == ["울릉도 + 실내"]


def test_a_headline_particle_follows_the_place_name_it_attaches_to() -> None:
    assert ask_service._subject_particle("우도") == "가"
    assert ask_service._subject_particle("오동도") == "가"
    assert ask_service._subject_particle("봉화은어축제") == "가"
    assert ask_service._subject_particle("성산일출봉") == "이"
    assert ask_service._subject_particle("한라산") == "이"


def test_a_zero_answer_without_a_region_does_not_tell_me_to_widen_one() -> None:
    intent = QueryIntent(moodHints=["lake"], crowdPreference="quiet")

    segments = ask_service._zero_answer(intent, axes=suggest_service.ALL_AXES)

    text = "".join(s.text for s in segments)
    assert text.startswith("분위기 + 한적 조건으로는 없어요.")
    assert "지역을 넓히면" not in text
    assert text.endswith(" 조건을 조금 바꿔서 다시 물어봐 주세요.")
    assert suggest_service.derive_for_zero(intent, has_coords=False) == []


def test_a_zero_answer_only_offers_widening_when_a_widen_chip_comes_with_it() -> None:
    intent = QueryIntent(regionHints=["울릉도"], indoorOnly=True)

    text = "".join(s.text for s in ask_service._zero_answer(intent, axes=suggest_service.ALL_AXES))

    assert "지역을 넓히면" in text
    assert [chip.label for chip in suggest_service.derive_for_zero(intent, has_coords=False)] == [
        suggest_service.WIDEN_REGION_LABEL
    ]
