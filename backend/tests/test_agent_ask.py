from __future__ import annotations

import tempfile
from collections.abc import Awaitable, Callable

import pytest
import pytest_asyncio
from fakeredis.aioredis import FakeRedis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import formparsers

from app.core.db import get_db
from app.core.redis import get_redis
from app.kto.client import get_kto
from app.main import app
from app.modules.agent import repositories
from app.modules.agent.errors import AgentIntentUnavailable
from app.modules.agent.repositories import CandidateRow, VectorMatchRow
from app.modules.agent.routes import MAX_BODY_BYTES
from app.modules.agent.schemas import ExtractedPlace, QueryIntent
from app.modules.agent.services import ask as ask_service
from app.modules.agent.services import intent as intent_service
from app.modules.agent.services import photo as photo_service
from app.modules.agent.services import retrieve

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

    assert near_card.tag is not None and near_card.tag.endswith("km")
    assert quiet_card.tag == "하위 10%"


def test_answer_emphasises_the_result_count() -> None:
    segments = ask_service._answer(
        _pool()[:4],
        intent=QueryIntent(),
        near=False,
        lat=None,
        lng=None,
    )

    assert [s.text for s in segments if s.emphasis] == ["4곳"]
    assert "이번 주말" not in "".join(s.text for s in segments)


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
async def test_ask_reports_no_results_when_nothing_matches(
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

    assert res.status_code == 422
    assert res.json()["error"]["code"] == "AGENT_NO_RESULTS"


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

    assert res.status_code == 422
    assert res.json()["error"]["code"] == "AGENT_NO_RESULTS"


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
async def test_vague_domestic_question_still_returns_spots(
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
    assert res.json()["data"]["spots"]


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


def test_answer_reports_a_zero_kilometre_distance() -> None:
    here = _row("c0", rate=10.0, percentile=10, lat=LAT, lng=LNG)

    segments = ask_service._answer(
        [here],
        intent=QueryIntent(nearMe=True),
        near=True,
        lat=LAT,
        lng=LNG,
    )

    assert "0.0km" in "".join(s.text for s in segments)


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


@pytest.mark.integration
async def test_legacy_condition_fields_are_ignored_not_rejected(
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
    assert [spot["contentId"] for spot in data["spots"]] == ["j1", "v1", "v2", "v3"]
    assert "이번 주말" not in "".join(seg["text"] for seg in data["answer"])
