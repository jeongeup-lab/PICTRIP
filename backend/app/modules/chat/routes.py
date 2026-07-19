"""CHT routes. Guest-open conversational discovery."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, status

from app.core.db import DbSession
from app.core.redis import RedisDep
from app.core.schemas import ok
from app.modules.chat.schemas import ChatTurnRequest
from app.modules.chat.services import run_turn

router = APIRouter(tags=["CHT · discovery chat"])


@router.post(
    "/chat/turn",
    status_code=status.HTTP_200_OK,
    summary="대화 1턴 — 조건 적재/제거 + grounded 추천 + 다음 고개",
)
async def chat_turn(
    body: ChatTurnRequest,
    session: DbSession,
    redis: RedisDep,
) -> dict[str, Any]:
    return ok(await run_turn(session, redis, body))
