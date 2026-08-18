from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from redis.asyncio import Redis

from app.core.db import AsyncSession
from app.core.logging import get_logger
from app.modules.agent import repositories
from app.modules.agent.schemas import AskContext, QueryIntent
from app.modules.map.services import reverse_geocode

logger = get_logger(__name__)

RegionSource = Literal["question", "context", "coords", "none"]


@dataclass(frozen=True, slots=True)
class ResolvedRegion:
    hints: list[str] = field(default_factory=list)
    source: RegionSource = "none"
    label: str | None = None

    @property
    def guessed(self) -> bool:
        return self.source == "coords"


async def _from_focused_card(session: AsyncSession, context: AskContext | None) -> list[str]:
    if context is None or context.focusContentId is None:
        return []
    briefs = await repositories.load_candidates_by_ids(session, [context.focusContentId])
    row = briefs.get(context.focusContentId)
    if row is None:
        return []
    return [part for part in (row.region_name, row.sigungu_name) if part][:1]


async def resolve(
    session: AsyncSession,
    redis: Redis,
    *,
    intent: QueryIntent,
    context: AskContext | None,
    lat: float | None,
    lng: float | None,
) -> ResolvedRegion:
    """지역을 한 번만 정한다.

    질문 > 직전 대화 > 좌표 순이다. 좌표가 앞서면 서울에서 제주 일정을 짜는 사용자에게
    서울을 권하게 된다 — 채팅에서는 직전 대화가 현재 위치보다 강한 신호다.
    """
    if intent.regionHints:
        return ResolvedRegion(hints=list(intent.regionHints), source="question")

    focused = await _from_focused_card(session, context)
    if focused:
        return ResolvedRegion(hints=focused, source="context")

    if context is not None and context.intent is not None and context.intent.regionHints:
        return ResolvedRegion(hints=list(context.intent.regionHints), source="context")

    if lat is not None and lng is not None:
        label = await reverse_geocode(redis, lat=lat, lng=lng)
        if label is not None:
            hint = label.sigungu or label.sido
            if hint:
                logger.info("agent.region.guessed", label=label.label)
                return ResolvedRegion(hints=[hint], source="coords", label=hint)

    return ResolvedRegion()
