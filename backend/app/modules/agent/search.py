"""검색 진입점. 어느 라우터를 태울지 여기서만 고른다.

services/ 바깥에 둔다 — toolloop 과 같은 이유로, services/ 안에 넣으면
services -> toolloop -> services 가 된다.
"""

from __future__ import annotations

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.logging import get_logger
from app.kto.client import KtoClient
from app.modules.agent import toolloop
from app.modules.agent.emitter import Emitter
from app.modules.agent.schemas import (
    AskAnchor,
    AskContext,
    AskResponse,
    QueryIntent,
    RefinePatch,
)
from app.modules.agent.services import ask as ask_service
from app.modules.agent.tools import ToolContext

logger = get_logger(__name__)


async def run(
    session: AsyncSession,
    redis: Redis,
    kto: KtoClient | None,
    *,
    question: str | None,
    lat: float | None,
    lng: float | None,
    image_bytes: bytes | None,
    image_mime: str | None,
    intent: QueryIntent | None = None,
    patch: RefinePatch | None = None,
    anchor: AskAnchor | None = None,
    context: AskContext | None = None,
    emitter: Emitter | None = None,
) -> AskResponse:
    if _takes_tools(
        question, image_bytes=image_bytes, intent=intent, anchor=anchor, context=context
    ):
        ctx = ToolContext(session=session, redis=redis, kto=kto, lat=lat, lng=lng)
        asked = (question or "").strip() or (
            toolloop.anchor_question(anchor) if anchor is not None else ""
        )
        trace = await toolloop.route(
            ctx,
            asked,
            context=context,
            emitter=emitter,
            opening=toolloop.anchor_call(anchor) if anchor is not None else None,
        )
        logger.info("agent.search.routed", router="tools", calls=trace.calls)
        return toolloop.respond(trace, lat=lat, lng=lng)

    return await ask_service.ask(
        session,
        redis,
        kto,
        question=question,
        lat=lat,
        lng=lng,
        image_bytes=image_bytes,
        image_mime=image_mime,
        intent=intent,
        patch=patch,
        anchor=anchor,
        context=context,
        emitter=emitter,
    )


def _takes_tools(
    question: str | None,
    *,
    image_bytes: bytes | None,
    intent: QueryIntent | None,
    anchor: AskAnchor | None,
    context: AskContext | None,
) -> bool:
    """루프는 자유문 질문과 카드 탭을 받는다 — 사진·칩 재생은 아직 기존 경로다."""
    if settings.AGENT_ROUTER != "tools":
        return False
    if image_bytes or intent:
        return False
    if anchor is not None:
        return toolloop.anchor_call(anchor) is not None
    return bool(question and question.strip())
