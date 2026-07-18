from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, status

from app.core.db import DbSession
from app.core.redis import RedisDep
from app.modules.plan.schemas import ChatRequest
from app.modules.plan.services import get_plan_payload, handle_chat
from app.security.jwt import OptionalUserId
from app.web.envelope import ok
from app.web.ratelimit import rate_limit

router = APIRouter(tags=["plan"])


@router.post(
    "/plan/chat",
    status_code=status.HTTP_200_OK,
    summary="플랜 에이전트 대화 (되묻기 → 일정 생성)",
    dependencies=[Depends(rate_limit(bucket="plan_chat", limit=10, window_seconds=60))],
)
async def plan_chat(
    body: ChatRequest,
    session: DbSession,
    redis: RedisDep,
    user_id: OptionalUserId,
) -> dict[str, Any]:
    res = await handle_chat(session, redis, req=body, user_id=user_id)
    return ok(res.model_dump())


@router.get("/plan/{plan_id}", summary="생성된 일정 재조회")
async def plan_get(plan_id: uuid.UUID, session: DbSession) -> dict[str, Any]:
    payload = await get_plan_payload(session, plan_id)
    return ok(payload)
