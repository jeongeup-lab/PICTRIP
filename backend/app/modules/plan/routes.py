from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, Form, UploadFile, status

from app.core.db import DbSession
from app.core.redis import RedisDep
from app.modules.plan.schemas import ChatRequest
from app.modules.plan.services import get_plan_payload, handle_chat
from app.modules.plan.services.photo import handle_photo
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


@router.post(
    "/plan/photo",
    status_code=status.HTTP_200_OK,
    summary="사진 업로드 → 분위기 설명 + 닮은 국내 여행지 매칭",
    dependencies=[Depends(rate_limit(bucket="plan_photo", limit=10, window_seconds=60))],
)
async def plan_photo(
    session: DbSession,
    redis: RedisDep,
    file: UploadFile = File(...),
    threadId: str | None = Form(default=None),
) -> dict[str, Any]:
    image_bytes = await file.read()
    res = await handle_photo(
        session,
        redis,
        thread_id=threadId,
        image_bytes=image_bytes,
        mime_type=file.content_type or "",
    )
    return ok(res.model_dump())


@router.get("/plan/{plan_id}", summary="생성된 일정 재조회")
async def plan_get(plan_id: uuid.UUID, session: DbSession) -> dict[str, Any]:
    payload = await get_plan_payload(session, plan_id)
    return ok(payload)
