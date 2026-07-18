from __future__ import annotations

import uuid

import pytest
from fakeredis.aioredis import FakeRedis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis
from app.main import app
from app.modules.plan import repositories
from app.modules.plan.llm import AgentTurn
from app.modules.plan.naver_local import NaverPlace
from app.modules.plan.schemas import ChatRequest
from app.modules.plan.services.chat import get_plan_payload, handle_chat
from app.web.errors import PlanAgentUnavailable, ResourceNotFound

ANCHOR_LAT, ANCHOR_LNG = 37.75, 128.90


async def _seed_spot(session: AsyncSession, cid: str, *, lat: float, lng: float) -> None:
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, first_image_url, "
            "show_flag, mapx, mapy, lcls_systm1) "
            "VALUES (:cid, 12, :t, :img, 1, :lng, :lat, 'HS')"
        ),
        {"cid": cid, "t": f"spot-{cid}", "img": f"http://kto/{cid}.jpg", "lng": lng, "lat": lat},
    )


def _turn_stub(monkeypatch, turn: AgentTurn | None):
    async def fake(**kwargs):
        return turn

    monkeypatch.setattr("app.modules.plan.services.chat.generate_turn", fake)


def _narrate_stub(monkeypatch):
    async def fake(**kwargs):
        return {"title": "강릉 당일치기", "summary": "요약", "replyText": "일정을 만들었어요."}

    monkeypatch.setattr("app.modules.plan.services.narrate.generate_json", fake)


def _candidates_stubs(monkeypatch):
    async def fake_place(query: str):
        return (ANCHOR_LAT, ANCHOR_LNG)

    async def fake_local(query: str, *, display: int = 5):
        if "카페" in query:
            return [
                NaverPlace("툇마루", "카페,디저트>카페", "강릉", ANCHOR_LAT + 0.002, ANCHOR_LNG)
            ]
        return [
            NaverPlace("초당순두부", "한식>두부요리", "강릉", ANCHOR_LAT + 0.001, ANCHOR_LNG),
            NaverPlace("동화가든", "한식>두부요리", "강릉", ANCHOR_LAT + 0.003, ANCHOR_LNG),
        ]

    async def fake_transit(**kwargs):
        return 15

    monkeypatch.setattr("app.modules.plan.services.candidates.search_place", fake_place)
    monkeypatch.setattr("app.modules.plan.services.candidates.search_local", fake_local)
    monkeypatch.setattr("app.modules.plan.services.assemble.transit_minutes", fake_transit)


async def test_plain_text_turn_replies_text(db_session, monkeypatch):
    _turn_stub(monkeypatch, AgentTurn(text="며칠 일정으로 다녀오세요?"))
    redis = FakeRedis(decode_responses=False)

    res = await handle_chat(
        db_session, redis, req=ChatRequest(message="강릉 가고 싶어"), user_id=None
    )
    assert res.reply.type == "text"
    assert "며칠" in res.reply.text
    assert res.threadId


async def test_create_plan_turn_generates_and_persists(db_session, monkeypatch):
    _turn_stub(
        monkeypatch,
        AgentTurn(
            call_name="create_plan",
            call_args={"region": "강릉", "days": 1, "party": "혼자", "mobility": "walk"},
        ),
    )
    _narrate_stub(monkeypatch)
    _candidates_stubs(monkeypatch)
    await _seed_spot(db_session, "a1", lat=ANCHOR_LAT + 0.004, lng=ANCHOR_LNG)
    await _seed_spot(db_session, "a2", lat=ANCHOR_LAT + 0.006, lng=ANCHOR_LNG)
    redis = FakeRedis(decode_responses=False)

    res = await handle_chat(
        db_session, redis, req=ChatRequest(message="혼자 강릉 당일치기"), user_id=None
    )
    assert res.reply.type == "plan"
    plan = res.reply.plan
    assert plan is not None
    assert plan.title == "강릉 당일치기"
    assert len(plan.days) == 1
    slots = plan.days[0].slots
    assert [s.label for s in slots] == ["오전", "점심", "오후", "카페", "저녁"]
    kto_slots = [s for s in slots if s.type == "attraction"]
    assert all(s.contentId and s.imageUrl for s in kto_slots)

    row = await repositories.get_plan(db_session, uuid.UUID(plan.planId))
    assert row is not None and row.thread_id == res.threadId

    payload = await get_plan_payload(db_session, uuid.UUID(plan.planId))
    assert payload["planId"] == plan.planId


async def test_create_plan_without_region_falls_back_to_ask(db_session, monkeypatch):
    _turn_stub(monkeypatch, AgentTurn(call_name="create_plan", call_args={"days": 2}))
    redis = FakeRedis(decode_responses=False)

    res = await handle_chat(db_session, redis, req=ChatRequest(message="일정 짜줘"), user_id=None)
    assert res.reply.type == "text"


async def test_create_plan_without_days_asks_duration(db_session, monkeypatch):
    _turn_stub(monkeypatch, AgentTurn(call_name="create_plan", call_args={"region": "강릉"}))
    redis = FakeRedis(decode_responses=False)

    res = await handle_chat(
        db_session, redis, req=ChatRequest(message="강릉 여행가고싶다"), user_id=None
    )
    assert res.reply.type == "text"
    assert res.reply.plan is None
    assert "강릉" in res.reply.text
    assert res.reply.chips == ["당일치기", "1박 2일", "2박 3일"]


async def test_create_plan_with_pool_shows_picker_then_generates_from_picks(
    db_session, monkeypatch
):
    _turn_stub(
        monkeypatch, AgentTurn(call_name="create_plan", call_args={"region": "강릉", "days": 1})
    )
    _narrate_stub(monkeypatch)
    _candidates_stubs(monkeypatch)
    for i in range(5):
        await _seed_spot(db_session, f"p{i}", lat=ANCHOR_LAT + 0.004 + i * 0.002, lng=ANCHOR_LNG)
    redis = FakeRedis(decode_responses=False)

    res = await handle_chat(
        db_session, redis, req=ChatRequest(message="강릉 당일치기"), user_id=None
    )
    assert res.reply.type == "pick"
    assert res.reply.pick is not None
    assert res.reply.pick.maxPicks == 2
    assert len(res.reply.pick.spots) >= 4
    assert all(s.imageUrl for s in res.reply.pick.spots)
    assert res.reply.chips == ["알아서 짜줘"]

    picked = [res.reply.pick.spots[3].contentId, res.reply.pick.spots[1].contentId]
    _turn_stub(monkeypatch, None)
    res2 = await handle_chat(
        db_session,
        redis,
        req=ChatRequest(threadId=res.threadId, message="이 사진들로 짜줘", picks=picked),
        user_id=None,
    )
    assert res2.reply.type == "plan"
    plan = res2.reply.plan
    assert plan is not None
    attraction_ids = {s.contentId for d in plan.days for s in d.slots if s.type == "attraction"}
    assert set(picked) <= attraction_ids


async def test_auto_message_after_picker_generates(db_session, monkeypatch):
    _turn_stub(
        monkeypatch, AgentTurn(call_name="create_plan", call_args={"region": "강릉", "days": 1})
    )
    _narrate_stub(monkeypatch)
    _candidates_stubs(monkeypatch)
    for i in range(5):
        await _seed_spot(db_session, f"q{i}", lat=ANCHOR_LAT + 0.004 + i * 0.002, lng=ANCHOR_LNG)
    redis = FakeRedis(decode_responses=False)

    res = await handle_chat(
        db_session, redis, req=ChatRequest(message="강릉 당일치기"), user_id=None
    )
    assert res.reply.type == "pick"

    _turn_stub(monkeypatch, None)
    res2 = await handle_chat(
        db_session,
        redis,
        req=ChatRequest(threadId=res.threadId, message="알아서 짜줘"),
        user_id=None,
    )
    assert res2.reply.type == "plan"


async def test_recommend_places_turn_returns_cards(db_session, monkeypatch):
    _turn_stub(
        monkeypatch,
        AgentTurn(call_name="recommend_places", call_args={"query": "어린이대공원역 카페"}),
    )

    async def fake_local(query: str, *, display: int = 5):
        assert "어린이대공원역" in query
        return [NaverPlace("카페 온도", "카페,디저트>카페", "서울 광진구", 37.548, 127.074)]

    monkeypatch.setattr("app.modules.plan.services.chat.search_local", fake_local)
    redis = FakeRedis(decode_responses=False)

    res = await handle_chat(
        db_session,
        redis,
        req=ChatRequest(message="어린이대공원역 근처 작업하기 좋은 카페 추천해줘"),
        user_id=None,
    )
    assert res.reply.type == "places"
    assert res.reply.places and res.reply.places[0].name == "카페 온도"
    assert res.reply.places[0].links.naver and "map.naver.com" in res.reply.places[0].links.naver


async def test_recommend_places_empty_returns_text(db_session, monkeypatch):
    _turn_stub(monkeypatch, AgentTurn(call_name="recommend_places", call_args={"query": "화성"}))

    async def fake_local(query: str, *, display: int = 5):
        return []

    monkeypatch.setattr("app.modules.plan.services.chat.search_local", fake_local)
    redis = FakeRedis(decode_responses=False)

    res = await handle_chat(db_session, redis, req=ChatRequest(message="화성 카페"), user_id=None)
    assert res.reply.type == "text"


async def test_raises_when_llm_unavailable(db_session, monkeypatch):
    _turn_stub(monkeypatch, None)
    redis = FakeRedis(decode_responses=False)

    with pytest.raises(PlanAgentUnavailable):
        await handle_chat(db_session, redis, req=ChatRequest(message="강릉"), user_id=None)


async def test_get_plan_payload_unknown_raises(db_session):
    with pytest.raises(ResourceNotFound):
        await get_plan_payload(db_session, uuid.uuid4())


async def test_chat_route_returns_envelope(client, monkeypatch):
    _turn_stub(monkeypatch, AgentTurn(text="어디로 떠나볼까요?"))
    redis = FakeRedis(decode_responses=False)
    app.dependency_overrides[get_redis] = lambda: redis
    try:
        resp = await client.post("/v1/plan/chat", json={"message": "여행 가고 싶다"})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body["error"] is None
    assert body["data"]["reply"]["type"] == "text"
    assert body["data"]["threadId"]


async def test_plan_get_route_unknown_returns_404(client):
    resp = await client.get(f"/v1/plan/{uuid.uuid4()}")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
