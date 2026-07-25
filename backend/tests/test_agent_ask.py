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
from app.modules.agent.schemas import AskFilters, QueryIntent
from app.modules.agent.services import ask as ask_service
from app.modules.agent.services import intent as intent_service
from app.modules.agent.services import retrieve

LAT, LNG = 35.15, 129.05


def _row(cid: str, *, rate: float | None, lat: float = LAT, lng: float = LNG) -> CandidateRow:
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
    )


def test_quiet_preference_keeps_the_least_crowded_slice() -> None:
    rows = [_row(f"c{i}", rate=float(i * 10)) for i in range(10)]

    kept = retrieve.filter_by_crowd(rows, "quiet")

    assert [row.content_id for row in kept] == ["c0", "c1", "c2"]


def test_popular_preference_keeps_the_most_crowded_slice() -> None:
    rows = [_row(f"c{i}", rate=float(i * 10)) for i in range(10)]

    kept = retrieve.filter_by_crowd(rows, "popular")

    assert [row.content_id for row in kept] == ["c9", "c8", "c7"]


def test_crowd_filter_is_a_no_op_without_concentration_rows() -> None:
    rows = [_row("a", rate=None), _row("b", rate=None)]

    assert retrieve.filter_by_crowd(rows, "quiet") == rows


def test_percentile_is_relative_to_the_candidate_pool() -> None:
    pool = [_row(f"c{i}", rate=float(i * 10)) for i in range(10)]

    assert retrieve.percentile(pool[0], pool) == 1
    assert retrieve.percentile(pool[5], pool) == 50


def test_crowd_label_buckets_by_rate() -> None:
    assert retrieve.crowd_label(_row("a", rate=90.0)) == "붐빔"
    assert retrieve.crowd_label(_row("b", rate=50.0)) == "보통"
    assert retrieve.crowd_label(_row("c", rate=10.0)) == "한산"
    assert retrieve.crowd_label(_row("d", rate=None)) is None


def test_region_filter_keeps_only_matching_address_prefixes() -> None:
    busan = _row("a", rate=None)
    seoul = CandidateRow(**{**busan.__dict__, "content_id": "b", "addr1": "서울특별시 종로구 1"})

    kept = ask_service._apply_region([busan, seoul], AskFilters(region="capital"))

    assert [row.content_id for row in kept] == ["b"]


def test_every_region_option_has_prefixes_except_all() -> None:
    assert retrieve.REGION_PREFIXES["all"] == ()
    for key, prefixes in retrieve.REGION_PREFIXES.items():
        if key != "all":
            assert prefixes, key


def test_card_tag_prefers_distance_then_percentile() -> None:
    pool = [_row(f"c{i}", rate=float(i * 10)) for i in range(10)]
    quiet = QueryIntent(crowdPreference="quiet")

    near_card = ask_service._card(pool[0], pool=pool, intent=quiet, lat=LAT, lng=LNG, near=True)
    quiet_card = ask_service._card(pool[0], pool=pool, intent=quiet, lat=None, lng=None, near=False)

    assert near_card.tag is not None and near_card.tag.endswith("km")
    assert quiet_card.tag == "하위 1%"


def test_answer_emphasises_the_result_count() -> None:
    pool = [_row(f"c{i}", rate=float(i * 10)) for i in range(10)]

    segments = ask_service._answer(
        pool[:4],
        pool,
        intent=QueryIntent(),
        filters=AskFilters(when="weekend"),
        near=False,
        lat=None,
        lng=None,
    )

    assert [s.text for s in segments if s.emphasis] == ["4곳"]
    assert "이번 주말" in "".join(s.text for s in segments)


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
            "INSERT INTO lcls_systm_codes "
            "(lcls_systm3_cd, lcls_systm2_cd, lcls_systm1_cd, lcls_systm3_nm, "
            "lcls_systm2_nm, lcls_systm1_nm) "
            "VALUES ('NA010100', 'NA01', 'NA', '계곡', '자연관광지', '자연') "
            "ON CONFLICT DO NOTHING"
        )
    )
    for cid, rate in (("v1", "12.00"), ("v2", "48.00"), ("v3", "88.00")):
        await session.execute(
            text(
                "INSERT INTO spots (content_id, content_type_id, title, addr1, "
                "first_image_url, show_flag, mapx, mapy, lcls_systm1, lcls_systm3, "
                "ldong_regn_cd, ldong_signgu_cd) "
                "VALUES (:cid, 12, :t, '부산광역시 사하구 1', 'http://kto/i.jpg', 1, "
                ":lng, :lat, 'NA', 'NA010100', '26', '26380')"
            ),
            {"cid": cid, "t": f"계곡-{cid}", "lng": LNG, "lat": LAT},
        )
        await session.execute(
            text(
                "INSERT INTO spot_concentration "
                "(content_id, concentration_rate, base_ymd, raw_name) "
                "VALUES (:cid, :rate, DATE '2026-07-01', :rn)"
            ),
            {"cid": cid, "rate": rate, "rn": f"n-{cid}"},
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
        return QueryIntent(categoryKeywords=["계곡"], crowdPreference="quiet")

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    _override(db_session)
    try:
        res = await client.post(
            "/v1/agent/ask",
            json={"question": "여름에 시원하고 사람 적은 계곡", "region": "gyeongsang"},
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
        res = await client.post("/v1/agent/ask", json={"region": "all"})
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 422
    assert res.json()["error"]["code"] == "VALIDATION_FAILED"


@pytest.mark.integration
async def test_ask_reports_no_results_when_nothing_matches(
    db_session, client, seeded, monkeypatch
) -> None:
    async def fake_intent(question: str) -> QueryIntent:
        return QueryIntent(categoryKeywords=["계곡"])

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    _override(db_session)
    try:
        res = await client.post("/v1/agent/ask", json={"question": "제주 계곡", "region": "jeju"})
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 422
    assert res.json()["error"]["code"] == "AGENT_NO_RESULTS"
