from __future__ import annotations

import json
import uuid
from typing import Any

from redis.asyncio import Redis

from app.core.db import AsyncSession
from app.core.logging import get_logger
from app.modules.plan import repositories
from app.modules.plan.links import place_links
from app.modules.plan.llm import generate_turn
from app.modules.plan.naver_local import search_local
from app.modules.plan.schemas import ChatReply, ChatRequest, ChatResponse, PlaceCard, PlanPayload
from app.modules.plan.services.assemble import assemble_days
from app.modules.plan.services.candidates import collect_candidates
from app.modules.plan.services.intent import PlanIntent, clamp_days
from app.modules.plan.services.narrate import narrate_plan
from app.web.errors import PlanAgentUnavailable, ResourceNotFound

logger = get_logger(__name__)

_THREAD_KEY = "plan:thread:{tid}"
_THREAD_TTL = 86_400
_MAX_THREAD_MESSAGES = 20
_MAX_CONTEXT_MESSAGES = 12

_SYSTEM = (
    "너는 PICTRIP AI, 한국 국내여행 도우미다. 항상 한국어 해요체로 짧게 답한다. 이모지 금지. "
    "도구 규칙: "
    "1) 사용자가 특정 지역의 여행 일정(코스)을 원하고 지역과 일수를 알 수 있으면 create_plan을 호출한다. "
    "당일치기=1, 1박 2일=2, 2박 3일=3, 상한 3. '주말'처럼 기간을 유추할 수 있으면 유추한다. "
    "2) 특정 장소·역·동네 주변의 맛집·카페·가볼 곳 같은 단건 추천 질문에는 recommend_places를 호출한다. "
    "query에는 위치와 조건을 그대로 담는다. 예: '어린이대공원역 작업하기 좋은 카페'. "
    "3) 일정을 만들기에 지역이나 기간이 부족하면 도구를 호출하지 말고 부족한 것 한 가지만 짧게 되묻는다. "
    "지역이 없는데 분위기(바다·산·먹방 등)를 말하면 어울리는 국내 지역 2~3곳을 예로 들며 되묻는다. "
    "4) 이미 만든 일정을 고쳐 달라고 하면 바뀐 조건을 반영해 create_plan을 다시 호출한다. "
    "5) 여행과 무관한 요청은 정중히 여행 얘기로 돌린다."
)

_TOOLS: list[dict[str, Any]] = [
    {
        "name": "create_plan",
        "description": "특정 지역의 여행 일정(일자별 코스)을 생성한다.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "region": {
                    "type": "STRING",
                    "description": "시·군 단위 지역명 또는 중심 장소. 예: 강릉, 전주, 어린이대공원역",
                },
                "days": {"type": "INTEGER", "description": "여행 일수 1~3"},
                "party": {"type": "STRING", "description": "동행. 예: 혼자, 커플, 부모님"},
                "mobility": {"type": "STRING", "enum": ["walk", "transit", "car"]},
                "themes": {"type": "ARRAY", "items": {"type": "STRING"}},
            },
            "required": ["region", "days"],
        },
    },
    {
        "name": "recommend_places",
        "description": "특정 위치 주변의 맛집·카페·가볼 곳을 단건 추천한다. 일정 생성이 아닐 때 사용.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {
                    "type": "STRING",
                    "description": "위치와 조건을 담은 검색어. 예: 어린이대공원역 작업하기 좋은 카페",
                }
            },
            "required": ["query"],
        },
    },
]

_FALLBACK_ASK = "어디로, 며칠 일정으로 다녀오실지 알려주시면 바로 짜드릴게요."
_PLACES_FOUND = "네이버에서 리뷰 많은 순으로 골라봤어요."
_PLACES_EMPTY = "마땅한 곳을 찾지 못했어요. 위치나 조건을 조금 바꿔서 다시 말해줄래요?"


async def _load_state(redis: Redis, tid: str) -> dict[str, Any]:
    try:
        raw = await redis.get(_THREAD_KEY.format(tid=tid))
    except Exception as exc:
        logger.warning("plan.thread.load_failed", error=str(exc))
        return {}
    if not raw:
        return {}
    try:
        text = raw.decode() if isinstance(raw, bytes) else raw
        state = json.loads(text)
    except (ValueError, TypeError) as exc:
        logger.warning("plan.thread.corrupt", error=str(exc))
        return {}
    return state if isinstance(state, dict) else {}


async def _save_state(redis: Redis, tid: str, state: dict[str, Any]) -> None:
    try:
        await redis.set(_THREAD_KEY.format(tid=tid), json.dumps(state), ex=_THREAD_TTL)
    except Exception as exc:
        logger.warning("plan.thread.save_failed", error=str(exc))


def _normalize_messages(raw: Any) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    if not isinstance(raw, list):
        return messages
    for item in raw:
        if isinstance(item, dict) and item.get("role") in ("user", "model") and item.get("text"):
            messages.append({"role": str(item["role"]), "text": str(item["text"])})
        elif isinstance(item, str):
            messages.append({"role": "user", "text": item})
    return messages


async def _generate(
    session: AsyncSession,
    *,
    tid: str,
    user_id: int | None,
    intent: PlanIntent,
) -> tuple[PlanPayload, str]:
    cand = await collect_candidates(session, intent)
    days = await assemble_days(intent, cand)
    texts = await narrate_plan(intent, days)
    plan_id = uuid.uuid4()
    payload = PlanPayload(
        planId=str(plan_id),
        title=texts["title"],
        summary=texts["summary"],
        region=intent.region or "",
        days=days,
    )
    await repositories.insert_plan(
        session,
        plan_id=plan_id,
        thread_id=tid,
        user_id=user_id,
        payload=payload.model_dump(),
    )
    return payload, texts["replyText"]


def _intent_from_args(args: dict[str, Any]) -> PlanIntent | None:
    region = str(args.get("region") or "").strip()
    if not region:
        return None
    mobility = args.get("mobility")
    themes = args.get("themes")
    party = args.get("party")
    return PlanIntent(
        region=region,
        days=clamp_days(args.get("days")) or 1,
        party=str(party).strip() or None if isinstance(party, str) else None,
        themes=[str(t) for t in themes if str(t).strip()] if isinstance(themes, list) else [],
        mobility=mobility if mobility in ("walk", "transit", "car") else None,
    )


async def _recommend_places(query: str) -> ChatReply:
    places = await search_local(query, display=5)
    cards = [
        PlaceCard(
            name=p.name,
            category=p.category,
            address=p.address,
            lat=p.lat,
            lng=p.lng,
            links=place_links(p.name, p.lat, p.lng),
        )
        for p in places
    ]
    if not cards:
        return ChatReply(type="text", text=_PLACES_EMPTY)
    return ChatReply(type="places", text=_PLACES_FOUND, places=cards)


async def handle_chat(
    session: AsyncSession,
    redis: Redis,
    *,
    req: ChatRequest,
    user_id: int | None,
) -> ChatResponse:
    tid = req.threadId or uuid.uuid4().hex
    state = await _load_state(redis, tid)
    messages = _normalize_messages(state.get("messages"))[-_MAX_THREAD_MESSAGES:]
    messages.append({"role": "user", "text": req.message})

    contents = [
        {"role": m["role"], "parts": [{"text": m["text"]}]}
        for m in messages[-_MAX_CONTEXT_MESSAGES:]
    ]
    turn = await generate_turn(system=_SYSTEM, contents=contents, tools=_TOOLS)
    if turn is None:
        raise PlanAgentUnavailable()

    if turn.call_name == "create_plan":
        intent = _intent_from_args(turn.call_args or {})
        if intent is None:
            reply = ChatReply(type="text", text=_FALLBACK_ASK)
        else:
            payload, reply_text = await _generate(session, tid=tid, user_id=user_id, intent=intent)
            state["planId"] = payload.planId
            reply = ChatReply(type="plan", text=reply_text, plan=payload)
    elif turn.call_name == "recommend_places":
        query = str((turn.call_args or {}).get("query") or req.message).strip()
        reply = await _recommend_places(query)
    else:
        reply = ChatReply(type="text", text=turn.text or _FALLBACK_ASK)

    messages.append({"role": "model", "text": reply.text})
    state["messages"] = messages[-_MAX_THREAD_MESSAGES:]
    await _save_state(redis, tid, state)
    return ChatResponse(threadId=tid, reply=reply)


async def get_plan_payload(session: AsyncSession, plan_id: uuid.UUID) -> dict[str, Any]:
    row = await repositories.get_plan(session, plan_id)
    if row is None:
        raise ResourceNotFound()
    return dict(row.payload)
