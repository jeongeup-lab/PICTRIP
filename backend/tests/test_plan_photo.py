from __future__ import annotations

import json

import pytest
from fakeredis.aioredis import FakeRedis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.plan.llm import AgentTurn
from app.modules.plan.naver_local import NaverPlace
from app.modules.plan.repositories import PhotoMatchRow
from app.modules.plan.schemas import ChatRequest, UserLocation
from app.modules.plan.services.chat import handle_chat
from app.modules.plan.services.photo import handle_photo
from app.web.errors import ImageInvalid

_ROWS = [
    PhotoMatchRow(
        "100", "경포해수욕장", "해변", "강원 강릉시", 37.80, 128.90, "http://kto/1.jpg", 0.18
    ),
    PhotoMatchRow(
        "200", "협재해수욕장", "해변", "제주 제주시", 33.39, 126.24, "http://kto/2.jpg", 0.22
    ),
]


def _photo_stubs(monkeypatch):
    monkeypatch.setattr(
        "app.modules.plan.services.photo.embedder.embed_image", lambda b: [0.1] * 512
    )

    async def fake_match(session, vector, *, limit):
        return list(_ROWS)

    async def fake_describe(image_bytes, mime_type):
        return "노을이 지는 바닷가 풍경이에요."

    monkeypatch.setattr("app.modules.plan.services.photo.match_spots_by_vector", fake_match)
    monkeypatch.setattr("app.modules.plan.services.photo.describe_image", fake_describe)


async def test_photo_returns_description_and_matches(db_session, monkeypatch):
    _photo_stubs(monkeypatch)
    redis = FakeRedis(decode_responses=False)

    res = await handle_photo(
        db_session, redis, thread_id=None, image_bytes=b"img", mime_type="image/jpeg"
    )
    assert "바닷가" in res.description
    assert [m.contentId for m in res.matches] == ["100", "200"]
    assert res.matches[0].similarity == pytest.approx(0.82)

    raw = await redis.get(f"plan:thread:{res.threadId}")
    state = json.loads(raw)
    assert [m["contentId"] for m in state["matches"]] == ["100", "200"]


async def test_photo_rejects_bad_mime(db_session):
    redis = FakeRedis(decode_responses=False)
    with pytest.raises(ImageInvalid):
        await handle_photo(
            db_session, redis, thread_id=None, image_bytes=b"x", mime_type="text/plain"
        )


async def _seed_state(redis: FakeRedis, tid: str) -> None:
    state = {
        "messages": [],
        "matches": [
            {"contentId": "100", "name": "경포해수욕장", "lat": 37.80, "lng": 128.90},
            {"contentId": "200", "name": "협재해수욕장", "lat": 33.39, "lng": 126.24},
        ],
    }
    await redis.set(f"plan:thread:{tid}", json.dumps(state))


async def test_nearest_matches_sorts_by_user_location(db_session, monkeypatch):
    async def fake_turn(**kwargs):
        return AgentTurn(call_name="nearest_matches", call_args={})

    monkeypatch.setattr("app.modules.plan.services.chat.generate_turn", fake_turn)
    redis = FakeRedis(decode_responses=False)
    await _seed_state(redis, "t1")

    res = await handle_chat(
        db_session,
        redis,
        req=ChatRequest(
            threadId="t1",
            message="내 위치에서 가까운 곳은?",
            location=UserLocation(lat=33.5, lng=126.5),
        ),
        user_id=None,
    )
    assert res.reply.type == "places"
    assert res.reply.places is not None
    assert res.reply.places[0].name == "협재해수욕장"


async def test_nearest_matches_without_location_asks_permission(db_session, monkeypatch):
    async def fake_turn(**kwargs):
        return AgentTurn(call_name="nearest_matches", call_args={})

    monkeypatch.setattr("app.modules.plan.services.chat.generate_turn", fake_turn)
    redis = FakeRedis(decode_responses=False)
    await _seed_state(redis, "t2")

    res = await handle_chat(
        db_session, redis, req=ChatRequest(threadId="t2", message="가까운 데는?"), user_id=None
    )
    assert res.reply.type == "text"
    assert "위치" in res.reply.text


async def test_recommend_retries_with_locality(db_session, monkeypatch):
    async def fake_turn(**kwargs):
        return AgentTurn(
            call_name="recommend_places", call_args={"query": "남애항 스카이워크 전망대 맛집"}
        )

    queries: list[str] = []

    async def fake_local(query: str, *, display: int = 5):
        queries.append(query)
        if "양양" in query:
            return [NaverPlace("남애복집", "한식", "강원 양양군", 38.02, 128.75)]
        return []

    monkeypatch.setattr("app.modules.plan.services.chat.generate_turn", fake_turn)
    monkeypatch.setattr("app.modules.plan.services.chat.search_local", fake_local)
    redis = FakeRedis(decode_responses=False)
    await redis.set(
        "plan:thread:t3",
        json.dumps(
            {
                "messages": [],
                "selected": {
                    "name": "남애항 스카이워크 전망대",
                    "address": "강원특별자치도 양양군 현남면",
                    "lat": 38.02,
                    "lng": 128.75,
                },
            }
        ),
    )

    res = await handle_chat(
        db_session, redis, req=ChatRequest(threadId="t3", message="근처 맛집 있어?"), user_id=None
    )
    assert res.reply.type == "places"
    assert res.reply.places and res.reply.places[0].name == "남애복집"
    assert any("양양" in q for q in queries)


async def test_recommend_falls_back_to_kto_when_naver_empty(db_session, monkeypatch):
    async def fake_turn(**kwargs):
        return AgentTurn(call_name="recommend_places", call_args={"query": "오지 맛집"})

    async def fake_local(query: str, *, display: int = 5):
        return []

    monkeypatch.setattr("app.modules.plan.services.chat.generate_turn", fake_turn)
    monkeypatch.setattr("app.modules.plan.services.chat.search_local", fake_local)
    await db_session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, first_image_url, "
            "show_flag, mapx, mapy, lcls_systm2, addr1) "
            "VALUES ('900', 39, '산골식당', 'http://kto/9.jpg', 1, 128.75, 38.02, 'FD01', '강원 양양군')"
        )
    )
    redis = FakeRedis(decode_responses=False)
    await redis.set(
        "plan:thread:t4",
        json.dumps(
            {
                "messages": [],
                "selected": {
                    "name": "전망대",
                    "address": "강원 양양군",
                    "lat": 38.02,
                    "lng": 128.75,
                },
            }
        ),
    )

    res = await handle_chat(
        db_session, redis, req=ChatRequest(threadId="t4", message="근처 맛집?"), user_id=None
    )
    assert res.reply.type == "places"
    assert res.reply.places and res.reply.places[0].source == "kto"
    assert res.reply.places[0].name == "산골식당"


async def test_recommend_cafe_filters_non_cafe_categories(db_session, monkeypatch):
    async def fake_turn(**kwargs):
        return AgentTurn(call_name="recommend_places", call_args={"query": "신림동 카페"})

    async def fake_local(query: str, *, display: int = 5):
        return [
            NaverPlace("쟝블랑제리", "카페,디저트>베이커리", "서울 관악구", 37.47, 126.95),
            NaverPlace("영풍문고 신림점", "쇼핑,유통>서점", "서울 관악구", 37.48, 126.93),
            NaverPlace("스타벅스 신림점", "카페,디저트>카페", "서울 관악구", 37.48, 126.93),
        ]

    monkeypatch.setattr("app.modules.plan.services.chat.generate_turn", fake_turn)
    monkeypatch.setattr("app.modules.plan.services.chat.search_local", fake_local)
    redis = FakeRedis(decode_responses=False)

    res = await handle_chat(
        db_session, redis, req=ChatRequest(message="작업하기 좋은 카페는?"), user_id=None
    )
    assert res.reply.type == "places"
    names = [p.name for p in res.reply.places or []]
    assert "영풍문고 신림점" not in names
    assert "스타벅스 신림점" in names


async def test_recommend_excludes_previously_shown_on_retry(db_session, monkeypatch):
    async def fake_turn(**kwargs):
        return AgentTurn(call_name="recommend_places", call_args={"query": "신림동 카페"})

    calls = {"n": 0}

    async def fake_local(query: str, *, display: int = 5):
        calls["n"] += 1
        return [
            NaverPlace("카페A", "카페,디저트>카페", "서울 관악구", 37.47, 126.95),
            NaverPlace("카페B", "카페,디저트>카페", "서울 관악구", 37.48, 126.93),
        ]

    monkeypatch.setattr("app.modules.plan.services.chat.generate_turn", fake_turn)
    monkeypatch.setattr("app.modules.plan.services.chat.search_local", fake_local)
    redis = FakeRedis(decode_responses=False)

    res1 = await handle_chat(
        db_session, redis, req=ChatRequest(message="신림동 카페 ㄱㄱ"), user_id=None
    )
    assert res1.reply.type == "places"

    res2 = await handle_chat(
        db_session,
        redis,
        req=ChatRequest(threadId=res1.threadId, message="다른 데는 없어?"),
        user_id=None,
    )
    assert res2.reply.type == "places"


async def test_distance_between_uses_selected_origin(db_session, monkeypatch):
    async def fake_turn(**kwargs):
        return AgentTurn(call_name="distance_between", call_args={"target": "이원식당"})

    monkeypatch.setattr("app.modules.plan.services.chat.generate_turn", fake_turn)
    redis = FakeRedis(decode_responses=False)
    await redis.set(
        "plan:thread:t5",
        json.dumps(
            {
                "messages": [],
                "selected": {
                    "name": "주벅배전망대",
                    "address": "충남 서산시",
                    "lat": 36.77,
                    "lng": 126.35,
                },
                "places": [
                    {"name": "이원식당", "lat": 36.86, "lng": 126.30, "address": "충남 태안군"}
                ],
            }
        ),
    )

    res = await handle_chat(
        db_session,
        redis,
        req=ChatRequest(threadId="t5", message="이원식당이랑 얼마나 떨어져있어?"),
        user_id=None,
    )
    assert res.reply.type == "text"
    assert "주벅배전망대" in res.reply.text and "km" in res.reply.text


async def test_select_spot_returns_intro_card(db_session: AsyncSession, monkeypatch):
    await db_session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, first_image_url, "
            "show_flag, mapx, mapy, lcls_systm1, addr1) "
            "VALUES ('300', 12, '경기전', 'http://kto/3.jpg', 1, 127.15, 35.81, 'HS', '전북 전주시')"
        )
    )

    async def fake_json(**kwargs):
        return {"intro": "조선 태조의 어진을 모신 곳이에요. 한옥마을 산책과 함께 둘러보기 좋아요."}

    monkeypatch.setattr("app.modules.plan.services.chat.generate_json", fake_json)
    redis = FakeRedis(decode_responses=False)

    res = await handle_chat(
        db_session,
        redis,
        req=ChatRequest(message="경기전 알려줘", selectId="300"),
        user_id=None,
    )
    assert res.reply.type == "spot"
    assert res.reply.spot is not None
    assert res.reply.spot.contentId == "300"
    assert res.reply.spot.imageUrl == "http://kto/3.jpg"
    assert "어진" in res.reply.text

    raw = await redis.get(f"plan:thread:{res.threadId}")
    assert json.loads(raw)["selected"]["contentId"] == "300"
