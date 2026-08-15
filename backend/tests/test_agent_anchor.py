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
from app.modules.agent.schemas import QueryIntent
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
    assert all(ask_service._is_distance_tag(spot["tag"]) for spot in data["spots"])
    assert data["refinements"] == []
    assert data["suggestions"] == []


@pytest.mark.integration
async def test_a_specific_dish_question_with_coords_keeps_only_title_evidence(
    db_session, client, anchor_seeded, monkeypatch
) -> None:
    from app.modules.agent.services import intent as intent_service

    await _spot(
        db_session,
        "f3",
        title="구좌삼겹살집",
        l1="FD",
        l2="FD01",
        l3=None,
        content_type=39,
        lat_offset=0.002,
    )

    async def fake_intent(question: str) -> QueryIntent:
        return QueryIntent(categoryKeywords=["맛집"])

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    _override(db_session)
    try:
        res = await client.post(
            "/v1/agent/ask",
            json={"question": "삼겹살집", "lat": ANCHOR_LAT, "lng": ANCHOR_LNG},
        )
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    data = res.json()["data"]
    assert [spot["contentId"] for spot in data["spots"]] == ["f3"]
    assert data["intent"]["categoryKeywords"] == ["맛집", "삼겹살"]


@pytest.mark.integration
async def test_a_specific_dish_question_keeps_its_title_constraint_after_focus_pivot(
    db_session, client, anchor_seeded, monkeypatch
) -> None:
    from app.modules.agent.services import intent as intent_service

    await _spot(
        db_session,
        "f3",
        title="구좌삼겹살집",
        l1="FD",
        l2="FD01",
        l3=None,
        content_type=39,
        lat_offset=0.002,
    )

    async def fake_intent(
        question: str, *, prior: QueryIntent | None = None, prior_spots: list[str] | None = None
    ) -> QueryIntent:
        return QueryIntent(categoryKeywords=["맛집"], originPlace="앵커스팟")

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    _override(db_session)
    try:
        res = await client.post(
            "/v1/agent/ask",
            json={
                "question": "거기 근처 삼겹살집은?",
                "context": {"spots": [{"contentId": "a1", "title": "앵커스팟"}]},
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    assert [spot["contentId"] for spot in res.json()["data"]["spots"]] == ["f3"]


@pytest.mark.integration
async def test_a_specific_dish_zero_after_focus_pivot_names_the_title_condition(
    db_session, client, anchor_seeded, monkeypatch
) -> None:
    from app.modules.agent.services import intent as intent_service

    async def fake_intent(
        question: str, *, prior: QueryIntent | None = None, prior_spots: list[str] | None = None
    ) -> QueryIntent:
        return QueryIntent(categoryKeywords=["맛집"], originPlace="앵커스팟")

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    _override(db_session)
    try:
        res = await client.post(
            "/v1/agent/ask",
            json={
                "question": "거기 근처 보쌈집은?",
                "context": {"spots": [{"contentId": "a1", "title": "앵커스팟"}]},
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    answer = "".join(part["text"] for part in res.json()["data"]["answer"])
    assert "상호에 요청한 음식명(보쌈)이 모두 들어간 곳을 찾지 못했어요" in answer
    assert "맛집이 없어요" not in answer


@pytest.mark.integration
async def test_a_specific_dish_zero_at_my_coords_names_the_title_condition(
    db_session, client, anchor_seeded, monkeypatch
) -> None:
    from app.modules.agent.services import intent as intent_service

    async def fake_intent(question: str) -> QueryIntent:
        return QueryIntent(categoryKeywords=["맛집"])

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    _override(db_session)
    try:
        res = await client.post(
            "/v1/agent/ask",
            json={"question": "보쌈집", "lat": ANCHOR_LAT, "lng": ANCHOR_LNG},
        )
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    answer = "".join(part["text"] for part in res.json()["data"]["answer"])
    assert "상호에 요청한 음식명(보쌈)이 모두 들어간 곳을 찾지 못했어요" in answer
    assert "맛집이 없어요" not in answer


@pytest.mark.integration
async def test_a_specific_dish_zero_around_a_named_origin_names_the_title_condition(
    db_session, anchor_seeded
) -> None:
    response = await ask_service._ask_around(
        db_session,
        "김녕미로공원",
        "food",
        lat=ANCHOR_LAT,
        lng=ANCHOR_LNG,
        steps=[],
        intent=QueryIntent(categoryKeywords=["맛집", "보쌈"]),
        title_terms=["보쌈"],
    )

    answer = "".join(part.text for part in response.answer)
    assert "상호에 요청한 음식명(보쌈)이 모두 들어간 곳을 찾지 못했어요" in answer
    assert "맛집이 없어요" not in answer


@pytest.mark.integration
async def test_a_specific_dish_zero_across_a_region_names_the_title_condition(
    db_session, anchor_seeded
) -> None:
    response = await ask_service._food_across_region(
        db_session,
        "food",
        ["제주특별자치도"],
        steps=[],
        intent=QueryIntent(categoryKeywords=["맛집", "보쌈"]),
        lat=None,
        lng=None,
        title_terms=["보쌈"],
    )

    answer = "".join(part.text for part in response.answer)
    assert "상호에 요청한 음식명(보쌈)이 모두 들어간 곳을 찾지 못했어요" in answer
    assert "등록된 맛집이 없어요" not in answer


@pytest.mark.integration
async def test_a_photoless_anchor_card_borrows_a_random_attraction_image(
    db_session, client, anchor_seeded
) -> None:
    await _spot(
        db_session,
        "f9",
        title="사진없는식당",
        l1="FD",
        l2="FD01",
        l3=None,
        content_type=39,
        lat_offset=0.002,
        image="",
    )
    _override(db_session)
    try:
        res = await _ask_anchor(client, "a1", "food")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    cards = {spot["contentId"]: spot for spot in res.json()["data"]["spots"]}
    assert cards["f9"]["imageUrl"] is None
    assert cards["f9"]["fallbackImageUrl"]
    assert cards["f1"]["imageUrl"]
    assert cards["f1"]["fallbackImageUrl"] is None


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


def _vec(*values: float) -> str:
    padded = [*values, *([0.0] * (512 - len(values)))]
    return "[" + ",".join(str(value) for value in padded) + "]"


async def _embed(session: AsyncSession, cid: str, vec: str) -> None:
    await session.execute(
        text("INSERT INTO spot_embeddings (content_id, embedding) VALUES (:c, :v)"),
        {"c": cid, "v": vec},
    )


@pytest.mark.integration
async def test_anchor_related_returns_embedding_neighbours_without_itself(
    db_session, client, anchor_seeded
) -> None:
    await _spot(db_session, "n2", title="만장굴", l1="NA", l2="NA01", l3=None, lat_offset=0.02)
    await _embed(db_session, "a1", _vec(1.0, 0.0))
    await _embed(db_session, "n1", _vec(0.9, 0.1))
    await _embed(db_session, "n2", _vec(0.0, 1.0))
    await db_session.flush()
    _override(db_session)
    try:
        res = await _ask_anchor(client, "a1", "related")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    data = res.json()["data"]
    assert [step["tool"] for step in data["steps"]] == ["related"]
    assert "김녕미로공원 연관 관광지" in data["steps"][0]["label"]
    assert [spot["contentId"] for spot in data["spots"]] == ["n1", "n2"]
    assert all(spot["tag"].startswith("유사도 ") for spot in data["spots"])
    assert data["tagBasis"] == "분위기 유사도 기준"
    assert "김녕미로공원" in "".join(part["text"] for part in data["answer"])
    assert data["refinements"] == []


@pytest.mark.integration
async def test_anchor_related_without_a_content_id_is_rejected(
    db_session, client, anchor_seeded
) -> None:
    _override(db_session)
    try:
        res = await client.post("/v1/agent/ask", json={"anchor": {"action": "related"}})
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 422
    assert res.json()["error"]["code"] == "VALIDATION_FAILED"


@pytest.mark.integration
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
    assert "내 위치 주변으로" in "".join(part["text"] for part in data["answer"])
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


@pytest.mark.integration
async def test_an_anchor_answer_says_what_its_distances_are_measured_from(
    db_session, client, anchor_seeded
) -> None:
    _override(db_session)
    try:
        res = await client.post(
            "/v1/agent/ask", json={"anchor": {"contentId": "a1", "action": "food"}}
        )
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    data = res.json()["data"]
    assert data["spots"]
    assert data["tagBasis"] == "직선거리 기준"


@pytest.mark.integration
async def test_a_coords_anchor_measures_from_my_location(db_session, client, anchor_seeded) -> None:
    _override(db_session)
    try:
        res = await client.post(
            "/v1/agent/ask",
            json={"anchor": {"action": "cafe"}, "lat": ANCHOR_LAT, "lng": ANCHOR_LNG},
        )
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    data = res.json()["data"]
    assert data["spots"]
    assert "내 위치" in "".join(segment["text"] for segment in data["answer"])
    assert data["tagBasis"] == "직선거리 기준"


@pytest.mark.integration
async def test_a_question_about_a_previous_spot_pivots_to_the_anchor_search(
    db_session, client, anchor_seeded, monkeypatch
) -> None:
    from app.modules.agent.services import intent as intent_service

    async def fake_intent(question, *, prior=None, prior_spots=None):  # type: ignore[no-untyped-def]
        return QueryIntent(categoryKeywords=["카페"], originPlace="앵커스팟")

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    _override(db_session)
    try:
        res = await client.post(
            "/v1/agent/ask",
            json={
                "question": "거기 근처 카페는?",
                "context": {"spots": [{"contentId": "a1", "title": "앵커스팟"}]},
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    data = res.json()["data"]
    assert "카페" in "".join(segment["text"] for segment in data["answer"])
    assert data["tagBasis"] == "직선거리 기준"
    assert data["intent"]["categoryKeywords"] == ["카페"]
    assert data["steps"][0]["tool"] == "intent"


@pytest.mark.integration
async def test_an_origin_the_context_never_carried_is_ignored(
    db_session, client, anchor_seeded, monkeypatch
) -> None:
    from app.modules.agent.services import intent as intent_service

    async def fake_intent(question, *, prior=None, prior_spots=None):  # type: ignore[no-untyped-def]
        return QueryIntent(categoryKeywords=["카페"], originPlace="없는이름")

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    _override(db_session)
    try:
        res = await client.post(
            "/v1/agent/ask",
            json={
                "question": "거기 근처 카페는?",
                "context": {"spots": [{"contentId": "a1", "title": "앵커스팟"}]},
            },
        )
    finally:
        app.dependency_overrides.clear()

    basis = (res.json().get("data") or {}).get("tagBasis") or ""
    assert basis != "직선거리 기준"


def test_an_anchor_with_nothing_nearby_is_an_answer_not_an_error() -> None:
    from app.modules.agent.services import ask as ask_service

    answer = ask_service.empty_anchor_response("그리스신화박물관", "food", prior_steps=[])

    assert answer.spots == []
    assert answer.totalCount == 0
    assert "그리스신화박물관" in "".join(part.text for part in answer.answer)
    assert "맛집" in "".join(part.text for part in answer.answer)


def test_a_focused_card_pivots_a_nearby_question_without_naming_it() -> None:
    from app.modules.agent.schemas import AskContext, AskContextSpot, QueryIntent
    from app.modules.agent.services import ask as ask_service

    context = AskContext(
        spots=[AskContextSpot(contentId="126198", title="통영 세병관")],
        focusContentId="126198",
    )
    intent = QueryIntent(nearMe=True, categoryKeywords=["카페"])

    pivot = ask_service._origin_anchor(intent, context)

    assert pivot is not None
    assert pivot.contentId == "126198"
    assert pivot.action == "cafe"


def test_a_nearby_question_without_a_focused_card_stays_a_search() -> None:
    from app.modules.agent.schemas import AskContext, AskContextSpot, QueryIntent
    from app.modules.agent.services import ask as ask_service

    context = AskContext(spots=[AskContextSpot(contentId="126198", title="통영 세병관")])

    assert ask_service._origin_anchor(QueryIntent(nearMe=True), context) is None


def test_a_focused_card_pivots_when_the_user_points_without_naming() -> None:
    from app.modules.agent.schemas import AskContext, AskContextSpot, QueryIntent
    from app.modules.agent.services import ask as ask_service

    context = AskContext(
        spots=[AskContextSpot(contentId="126198", title="통영 세병관")],
        focusContentId="126198",
    )
    intent = QueryIntent(aroundOrigin=True, categoryKeywords=["맛집"])

    pivot = ask_service._origin_anchor(intent, context)

    assert pivot is not None
    assert pivot.contentId == "126198"
    assert pivot.action == "food"


def test_pointing_without_a_focused_card_stays_a_search() -> None:
    from app.modules.agent.schemas import AskContext, AskContextSpot, QueryIntent
    from app.modules.agent.services import ask as ask_service

    context = AskContext(spots=[AskContextSpot(contentId="126198", title="통영 세병관")])

    assert ask_service._origin_anchor(QueryIntent(aroundOrigin=True), context) is None


def test_naming_a_new_region_beats_a_stale_anchor() -> None:
    from app.modules.agent.schemas import AskContext, AskContextSpot, QueryIntent
    from app.modules.agent.services import ask as ask_service

    context = AskContext(
        intent=QueryIntent(regionHints=["통영"]),
        spots=[AskContextSpot(contentId="126198", title="통영 세병관")],
        focusContentId="126198",
    )
    intent = QueryIntent(aroundOrigin=True, regionHints=["부산"], categoryKeywords=["카페"])

    assert ask_service._origin_anchor(intent, context) is None


def test_a_region_carried_from_the_previous_turn_does_not_block_the_pivot() -> None:
    from app.modules.agent.schemas import AskContext, AskContextSpot, QueryIntent
    from app.modules.agent.services import ask as ask_service

    context = AskContext(
        intent=QueryIntent(regionHints=["통영"]),
        spots=[AskContextSpot(contentId="126198", title="통영 세병관")],
        focusContentId="126198",
    )
    intent = QueryIntent(aroundOrigin=True, regionHints=["통영"], categoryKeywords=["카페"])

    pivot = ask_service._origin_anchor(intent, context)

    assert pivot is not None and pivot.action == "cafe"


def test_naming_the_origin_still_pivots_even_with_a_region() -> None:
    from app.modules.agent.schemas import AskContext, AskContextSpot, QueryIntent
    from app.modules.agent.services import ask as ask_service

    context = AskContext(
        spots=[AskContextSpot(contentId="126198", title="통영 세병관")],
        focusContentId="126198",
    )
    intent = QueryIntent(originPlace="통영 세병관", regionHints=["통영"])

    pivot = ask_service._origin_anchor(intent, context)

    assert pivot is not None and pivot.contentId == "126198"


def test_an_anchor_answer_leads_with_the_nearest_distance() -> None:
    segments = ask_service._anchor_lead("성산일출봉", "food", nearest_m=420)

    text = "".join(s.text for s in segments)
    assert text.startswith("가장 가까운 맛집이 420m 거리예요.")
    assert [s.text for s in segments if s.emphasis] == ["420m"]


def test_a_sub_kilometre_distance_reads_in_metres_not_zero_point_something() -> None:
    assert ask_service._meters_label(38.0) == "40m"
    assert ask_service._meters_label(874.0) == "870m"
    assert ask_service._meters_label(4.0) == "10m"


def test_a_kilometre_scale_distance_keeps_the_kilometre_form() -> None:
    assert ask_service._meters_label(1000.0) == "1.0km"
    assert ask_service._meters_label(3210.0) == "3.2km"
    assert ask_service._meters_label(996.0) == "1.0km"


def test_a_close_anchor_never_leads_with_a_zero_distance() -> None:
    segments = ask_service._anchor_lead("성산일출봉", "cafe", nearest_m=32.0)

    assert "".join(s.text for s in segments) == "가장 가까운 카페가 30m 거리예요."


def test_an_anchor_answer_without_a_distance_states_the_scope() -> None:
    segments = ask_service._anchor_lead("성산일출봉", "cafe", nearest_m=None)

    assert "".join(s.text for s in segments) == "성산일출봉 주변 카페예요."


def test_an_anchor_answer_attaches_the_particle_each_noun_actually_takes() -> None:
    leads = {
        action: "".join(
            part.text for part in ask_service._anchor_lead("성산일출봉", action, nearest_m=420)
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
            for part in ask_service.empty_anchor_response(
                "성산일출봉", action, prior_steps=[]
            ).answer
        )
        for action in ("food", "cafe", "nearby")
    }

    assert "안에는 맛집이 없어요." in lines["food"]
    assert "안에는 카페가 없어요." in lines["cafe"]
    assert "안에는 볼거리가 없어요." in lines["nearby"]


def test_an_empty_region_line_attaches_the_particle_each_noun_takes() -> None:
    lines = {
        action: "".join(
            part.text
            for part in ask_service.food_in_region(
                [], ["부산광역시"], action, steps=[], intent=QueryIntent()
            ).answer
        )
        for action in ("food", "cafe", "nearby")
    }

    assert lines["food"] == "부산광역시에는 등록된 맛집이 없어요."
    assert lines["cafe"] == "부산광역시에는 등록된 카페가 없어요."
    assert lines["nearby"] == "부산광역시에는 등록된 볼거리가 없어요."


def test_an_anchor_scope_line_ends_with_the_copula_each_noun_takes() -> None:
    scopes = {
        action: "".join(
            part.text for part in ask_service._anchor_lead("성산일출봉", action, nearest_m=None)
        )
        for action in ("food", "cafe", "nearby")
    }

    assert scopes["food"] == "성산일출봉 주변 맛집이에요."
    assert scopes["cafe"] == "성산일출봉 주변 카페예요."
    assert scopes["nearby"] == "성산일출봉 주변 볼거리예요."
