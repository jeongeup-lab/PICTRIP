"""CHT routes. Guest-open conversational discovery."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, status

from app.core.db import DbSession
from app.core.redis import RedisDep
from app.core.schemas import ok
from app.modules.chat.schemas import (
    ChatMoodCover,
    ChatMoodCoversRequest,
    ChatMoodCoversResponse,
    ChatTurnRequest,
)
from app.modules.chat.services import mood_covers, run_turn

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


@router.post(
    "/chat/mood-covers",
    status_code=status.HTTP_200_OK,
    summary="무드 칩 대표 커버 — 각 발화의 첫 후보 이미지",
)
async def chat_mood_covers(
    body: ChatMoodCoversRequest,
    session: DbSession,
) -> dict[str, Any]:
    pairs = await mood_covers(session, body.utterances)
    return ok(
        ChatMoodCoversResponse(
            covers=[ChatMoodCover(utterance=u, coverUrl=url) for u, url in pairs]
        )
    )
