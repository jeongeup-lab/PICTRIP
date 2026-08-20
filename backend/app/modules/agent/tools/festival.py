from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.modules.agent import repositories
from app.modules.agent.errors import AgentFestivalUnavailable
from app.modules.agent.schemas import MAX_REGION_HINTS
from app.modules.agent.services import answer as answer_service
from app.modules.agent.services import retrieve
from app.modules.agent.tools.base import (
    Tool,
    ToolContext,
    ToolResult,
    describe,
    recoverable,
    strings,
)
from app.modules.feed import services as feed_services
from app.modules.spots.services import load_active_spot_cards_by_ids
from app.web.errors import AppError

FETCH_BUDGET_SECONDS = 3.0
_NONE_TODAY = "오늘 열리는 축제가 없습니다."


async def _festival(ctx: ToolContext, args: Mapping[str, Any]) -> ToolResult:
    if ctx.kto is None:
        raise AgentFestivalUnavailable()
    try:
        pool = await feed_services.load_festival_pool(
            ctx.redis, ctx.kto, fetch_timeout=FETCH_BUDGET_SECONDS
        )
    except (AppError, TimeoutError) as exc:
        raise AgentFestivalUnavailable() from exc

    openable = await _openable(ctx, pool)
    nationwide = answer_service.keep(pool, openable)
    hints = strings(args, "regions", limit=MAX_REGION_HINTS)
    cards = nationwide
    note = ""
    if hints:
        scoped = answer_service.keep(answer_service.match_region(pool, hints), openable)
        if scoped:
            cards = scoped
        else:
            note = f" ({hints[0]} 에는 없어 전국에서 골랐습니다)"

    content_ids = [card.content_id for card in cards[: retrieve.RESULT_LIMIT] if card.content_id]
    briefs = await repositories.load_candidates_by_ids(ctx.session, content_ids)
    rows = [briefs[cid] for cid in content_ids if cid in briefs]
    return ToolResult(rows=rows, observation=describe(rows, empty=_NONE_TODAY) + note)


async def _openable(ctx: ToolContext, cards: list[Any]) -> set[str]:
    content_ids = [card.content_id for card in cards if card.content_id]
    if not content_ids:
        return set()
    return set(await load_active_spot_cards_by_ids(ctx.session, content_ids))


FESTIVAL = Tool(
    name="festival",
    description=(
        "오늘 열리는 축제를 찾는다. '지금 열리는 축제', '이번 주 축제' 같은 질문에 쓴다. "
        "일반 관광지 검색에는 쓰지 않는다."
    ),
    parameters={
        "type": "object",
        "properties": {
            "regions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "시도·시군구 이름. 비우면 전국.",
            }
        },
    },
    label=lambda _args: "오늘 열리는 축제 조회",
    run=recoverable(_festival),
)
