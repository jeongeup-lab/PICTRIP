from __future__ import annotations

import json
import uuid
from typing import Any

from redis.asyncio import Redis

from app.core.db import AsyncSession
from app.core.logging import get_logger
from app.modules.plan import repositories
from app.modules.plan.schemas import ChatReply, ChatRequest, ChatResponse, PlanPayload
from app.modules.plan.services.assemble import assemble_days
from app.modules.plan.services.candidates import collect_candidates
from app.modules.plan.services.intent import PlanIntent, extract_intent
from app.modules.plan.services.narrate import narrate_plan
from app.web.errors import PlanAgentUnavailable, ResourceNotFound

logger = get_logger(__name__)

_THREAD_KEY = "plan:thread:{tid}"
_THREAD_TTL = 86_400
_MAX_THREAD_MESSAGES = 20

_REGION_CLARIFY_TEXT = "요즘 반응 좋은 곳으로 몇 군데 추려봤어요. 끌리는 곳을 골라보세요."
_REGION_CHIPS = ["강릉", "전주", "경주", "부산", "제주"]
_DAYS_CLARIFY_TEXT = "좋아요, {region}로 잡을게요. 며칠 일정으로 다녀오세요?"
_DAYS_CHIPS = ["당일치기", "1박 2일", "2박 3일"]


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


async def handle_chat(
    session: AsyncSession,
    redis: Redis,
    *,
    req: ChatRequest,
    user_id: int | None,
) -> ChatResponse:
    tid = req.threadId or uuid.uuid4().hex
    state = await _load_state(redis, tid)
    messages = [str(m) for m in state.get("messages", [])][-_MAX_THREAD_MESSAGES:]
    messages.append(req.message)
    state["messages"] = messages

    intent = await extract_intent(previous=state.get("intent"), messages=messages)
    if intent is None:
        raise PlanAgentUnavailable()
    state["intent"] = intent.to_dict()

    if not intent.region:
        reply = ChatReply(type="clarify", text=_REGION_CLARIFY_TEXT, chips=_REGION_CHIPS)
    elif not intent.days:
        reply = ChatReply(
            type="clarify",
            text=_DAYS_CLARIFY_TEXT.format(region=intent.region),
            chips=_DAYS_CHIPS,
        )
    else:
        payload, reply_text = await _generate(session, tid=tid, user_id=user_id, intent=intent)
        state["planId"] = payload.planId
        reply = ChatReply(type="plan", text=reply_text, plan=payload)

    await _save_state(redis, tid, state)
    return ChatResponse(threadId=tid, reply=reply)


async def get_plan_payload(session: AsyncSession, plan_id: uuid.UUID) -> dict[str, Any]:
    row = await repositories.get_plan(session, plan_id)
    if row is None:
        raise ResourceNotFound()
    return dict(row.payload)
