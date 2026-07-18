from __future__ import annotations

import uuid

import pytest
from fakeredis.aioredis import FakeRedis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis
from app.main import app
from app.modules.plan import repositories
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


def _intent_stub(monkeypatch, payload: dict | None):
    async def fake(**kwargs):
        return payload

    monkeypatch.setattr("app.modules.plan.services.intent.generate_json", fake)


def _narrate_stub(monkeypatch):
    async def fake(**kwargs):
        return {"title": "강릉 당일치기", "summary": "요약", "replyText": "일정을 만들었어요."}

    monkeypatch.setattr("app.modules.plan.services.narrate.generate_json", fake)


def _candidates_stubs(monkeypatch):
    async def fake_place(query: str):
        return (ANCHOR_LAT, ANCHOR_LNG)

    async def fake_local(query: str, *, display: int = 5):
        if "카페" in query:
            return [NaverPlace("툇마루", "카페", "강릉", ANCHOR_LAT + 0.002, ANCHOR_LNG)]
        return [
            NaverPlace("초당순두부", "한식", "강릉", ANCHOR_LAT + 0.001, ANCHOR_LNG),
            NaverPlace("중앙시장", "시장", "강릉", ANCHOR_LAT + 0.003, ANCHOR_LNG),
        ]

    async def fake_transit(**kwargs):
        return 15

    monkeypatch.setattr("app.modules.plan.services.candidates.search_place", fake_place)
    monkeypatch.setattr("app.modules.plan.services.candidates.search_local", fake_local)
    monkeypatch.setattr("app.modules.plan.services.assemble.transit_minutes", fake_transit)


async def test_clarifies_region_when_missing(db_session, monkeypatch):
    _intent_stub(monkeypatch, {"region": None, "days": None, "themes": []})
    redis = FakeRedis(decode_responses=False)

    res = await handle_chat(
        db_session, redis, req=ChatRequest(message="이번 주말에 어디 가지?"), user_id=None
    )
    assert res.reply.type == "clarify"
    assert res.reply.chips and "강릉" in res.reply.chips
    assert res.threadId


async def test_clarifies_days_when_missing(db_session, monkeypatch):
    _intent_stub(monkeypatch, {"region": "강릉", "days": None, "themes": []})
    redis = FakeRedis(decode_responses=False)

    res = await handle_chat(
        db_session, redis, req=ChatRequest(message="강릉 가고 싶어"), user_id=None
    )
    assert res.reply.type == "clarify"
    assert res.reply.chips == ["당일치기", "1박 2일", "2박 3일"]
    assert "강릉" in res.reply.text


async def test_generates_plan_and_persists(db_session, monkeypatch):
    _intent_stub(
        monkeypatch,
        {"region": "강릉", "days": 1, "party": "혼자", "themes": ["바다"], "mobility": "walk"},
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
    assert plan.region == "강릉"
    assert len(plan.days) == 1
    slots = plan.days[0].slots
    assert [s.label for s in slots] == ["오전", "점심", "오후", "카페", "저녁"]
    kto_slots = [s for s in slots if s.source == "kto"]
    assert all(s.contentId and s.imageUrl for s in kto_slots)

    row = await repositories.get_plan(db_session, uuid.UUID(plan.planId))
    assert row is not None and row.thread_id == res.threadId

    payload = await get_plan_payload(db_session, uuid.UUID(plan.planId))
    assert payload["planId"] == plan.planId


async def test_raises_when_llm_unavailable(db_session, monkeypatch):
    _intent_stub(monkeypatch, None)
    redis = FakeRedis(decode_responses=False)

    with pytest.raises(PlanAgentUnavailable):
        await handle_chat(db_session, redis, req=ChatRequest(message="강릉"), user_id=None)


async def test_get_plan_payload_unknown_raises(db_session):
    with pytest.raises(ResourceNotFound):
        await get_plan_payload(db_session, uuid.uuid4())


async def test_chat_route_returns_envelope(client, monkeypatch):
    _intent_stub(monkeypatch, {"region": None, "days": None, "themes": []})
    redis = FakeRedis(decode_responses=False)
    app.dependency_overrides[get_redis] = lambda: redis
    try:
        resp = await client.post("/v1/plan/chat", json={"message": "어디 가지?"})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body["error"] is None
    assert body["data"]["reply"]["type"] == "clarify"
    assert body["data"]["threadId"]


async def test_plan_get_route_unknown_returns_404(client):
    resp = await client.get(f"/v1/plan/{uuid.uuid4()}")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
