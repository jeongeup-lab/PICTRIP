"""검색 진입점.

services/ 바깥에 둔다 — toolloop 과 같은 이유로, services/ 안에 넣으면
services -> toolloop -> services 가 된다.
"""

from __future__ import annotations

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.kto.client import KtoClient
from app.modules.agent import toolloop
from app.modules.agent.emitter import Emitter
from app.modules.agent.routing import ToolCall
from app.modules.agent.schemas import (
    AskAnchor,
    AskContext,
    AskResponse,
    QueryIntent,
    RefinePatch,
)
from app.modules.agent.services import refine as refine_service
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
    user_id: int | None = None,
) -> AskResponse:
    ctx = ToolContext(
        session=session,
        redis=redis,
        kto=kto,
        lat=lat,
        lng=lng,
        image_bytes=image_bytes,
        image_mime=image_mime,
        user_id=user_id,
    )
    asked = (question or "").strip() or _implied_question(anchor, image_bytes, intent)
    trace = await toolloop.route(
        ctx,
        asked,
        context=context,
        emitter=emitter,
        opening=_opening(anchor, image_bytes, intent, patch),
    )
    logger.info("agent.search.routed", calls=trace.calls, stopped=trace.stopped)
    return toolloop.respond(trace, lat=lat, lng=lng)


def _implied_question(
    anchor: AskAnchor | None, image_bytes: bytes | None, intent: QueryIntent | None
) -> str:
    if anchor is not None:
        return toolloop.anchor_question(anchor)
    if image_bytes:
        return "이 사진과 닮은 국내 여행지를 알려줘."
    if intent is None:
        return ""
    return (
        "사용자가 조건을 바꿔 다시 찾아달라고 눌렀다. 바뀐 조건은 이미 첫 호출에 실려 있다. "
        "결과가 있으면 그대로 끝내라."
    )


def _opening(
    anchor: AskAnchor | None,
    image_bytes: bytes | None,
    intent: QueryIntent | None,
    patch: RefinePatch | None,
) -> ToolCall | None:
    """첨부·탭·칩은 사실이다 — 무슨 도구를 부를지 모델에게 묻지 않는다."""
    if anchor is not None:
        return toolloop.anchor_call(anchor)
    if image_bytes:
        return ToolCall(name="uploaded_photo", args={})
    if intent is not None:
        return toolloop.call_from_intent(refine_service.apply_patch(intent, patch))
    return None
