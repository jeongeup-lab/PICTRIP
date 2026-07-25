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
from app.modules.agent.errors import AgentIntentUnavailable
from app.modules.agent.repositories import CandidateRow, VectorMatchRow
from app.modules.agent.schemas import AskFilters, QueryIntent
from app.modules.agent.services import ask as ask_service
from app.modules.agent.services import intent as intent_service
from app.modules.agent.services import photo as photo_service
from app.modules.agent.services import retrieve

LAT, LNG = 35.15, 129.05


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


def test_region_filter_keeps_only_matching_address_prefixes() -> None:
    busan = _row("a", rate=None)
    seoul = CandidateRow(**{**busan.__dict__, "content_id": "b", "addr1": "서울특별시 종로구 1"})

    kept = ask_service._apply_prefixes([busan, seoul], ["서울", "경기", "인천"])

    assert [row.content_id for row in kept] == ["b"]


def test_every_region_option_has_prefixes_except_all() -> None:
    assert retrieve.REGION_PREFIXES["all"] == ()
    for key, prefixes in retrieve.REGION_PREFIXES.items():
        if key != "all":
            assert prefixes, key


def test_card_tag_prefers_distance_then_percentile() -> None:
    pool = _pool()
    quiet = QueryIntent(crowdPreference="quiet")

    near_card = ask_service._card(pool[0], intent=quiet, lat=LAT, lng=LNG, near=True)
    quiet_card = ask_service._card(pool[0], intent=quiet, lat=None, lng=None, near=False)

    assert near_card.tag is not None and near_card.tag.endswith("km")
    assert quiet_card.tag == "하위 10%"


def test_answer_emphasises_the_result_count() -> None:
    segments = ask_service._answer(
        _pool()[:4],
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
        res = await client.post(
            "/v1/agent/ask", json={"question": "강원 계곡", "region": "gangwon"}
        )
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 422
    assert res.json()["error"]["code"] == "AGENT_NO_RESULTS"


@pytest.mark.integration
async def test_question_region_hint_narrows_the_search_without_a_sheet_filter(
    db_session, client, seeded, monkeypatch
) -> None:
    async def fake_intent(question: str) -> QueryIntent:
        return QueryIntent(categoryKeywords=["계곡"], regionHints=["제주"])

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    _override(db_session)
    try:
        res = await client.post("/v1/agent/ask", json={"question": "제주 계곡", "region": "all"})
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    data = res.json()["data"]
    assert [spot["contentId"] for spot in data["spots"]] == ["j1"]
    assert data["totalCount"] == 1


@pytest.mark.integration
async def test_near_me_orders_candidates_by_distance_in_sql(
    db_session, client, seeded, monkeypatch
) -> None:
    async def fake_intent(question: str) -> QueryIntent:
        return QueryIntent(categoryKeywords=["계곡"], nearMe=True)

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    _override(db_session)
    try:
        res = await client.post(
            "/v1/agent/ask",
            json={"question": "근처 계곡", "region": "gyeongsang", "lat": LAT, "lng": LNG},
        )
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    data = res.json()["data"]
    assert [spot["contentId"] for spot in data["spots"]] == ["v3", "v2", "v1"]
    assert [step["tool"] for step in data["steps"]][-1] == "nearby"
    assert all(spot["tag"].endswith("km") for spot in data["spots"])


@pytest.mark.integration
async def test_quiet_percentile_comes_from_sql_not_the_truncated_pool(
    db_session, client, seeded, monkeypatch
) -> None:
    async def fake_intent(question: str) -> QueryIntent:
        return QueryIntent(categoryKeywords=["계곡"], crowdPreference="quiet")

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    _override(db_session)
    try:
        res = await client.post("/v1/agent/ask", json={"question": "한적한 계곡", "region": "all"})
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    spots = res.json()["data"]["spots"]
    assert spots[0]["contentId"] == "v1"
    assert spots[0]["tag"] == "하위 25%"


@pytest.mark.integration
async def test_photo_query_applies_the_region_hint_from_the_attached_text(
    db_session, client, seeded, monkeypatch
) -> None:
    async def fake_intent(question: str) -> QueryIntent:
        return QueryIntent(regionHints=["제주"])

    async def fake_match(session, *, image_bytes, image_mime):
        return [
            VectorMatchRow(
                content_id=cid,
                title=f"t-{cid}",
                category=None,
                addr1=None,
                lat=None,
                lng=None,
                image_url=None,
                cpyrht_div_cd=None,
                distance=0.2,
            )
            for cid in ("v1", "j1")
        ]

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    monkeypatch.setattr(photo_service, "match_photo", fake_match)
    _override(db_session)
    try:
        res = await client.post(
            "/v1/agent/ask",
            files={"photo": ("a.jpg", b"x", "image/jpeg")},
            data={"question": "제주에서 이런 분위기", "region": "all"},
        )
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    data = res.json()["data"]
    assert [spot["contentId"] for spot in data["spots"]] == ["j1"]
    assert [step["tool"] for step in data["steps"]] == ["intent", "photo_match", "region_filter"]


@pytest.mark.integration
async def test_unmatched_category_keyword_falls_back_to_title_search(
    db_session, client, seeded, monkeypatch
) -> None:
    async def fake_intent(question: str) -> QueryIntent:
        return QueryIntent(categoryKeywords=["계곡-v2"])

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    _override(db_session)
    try:
        res = await client.post("/v1/agent/ask", json={"question": "계곡-v2", "region": "all"})
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    data = res.json()["data"]
    assert [step["tool"] for step in data["steps"]] == ["intent", "title_search"]
    assert data["spots"][0]["contentId"] == "v2"


@pytest.mark.integration
async def test_unmatched_keyword_with_no_title_hit_does_not_widen_to_everything(
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
async def test_photo_query_survives_intent_extraction_failure(
    db_session, client, seeded, monkeypatch
) -> None:
    async def failing_intent(question: str) -> QueryIntent:
        raise AgentIntentUnavailable()

    async def fake_match(session, *, image_bytes, image_mime):
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
    monkeypatch.setattr(photo_service, "match_photo", fake_match)
    _override(db_session)
    try:
        res = await client.post(
            "/v1/agent/ask",
            files={"photo": ("a.jpg", b"x", "image/jpeg")},
            data={"question": "이 사진 같은 분위기의 여행지", "region": "all"},
        )
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    data = res.json()["data"]
    assert [step["tool"] for step in data["steps"]] == ["photo_match"]
    assert data["spots"][0]["contentId"] == "v1"
