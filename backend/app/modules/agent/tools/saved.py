from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.modules.agent import repositories
from app.modules.agent.repositories import CandidateRow
from app.modules.agent.schemas import MAX_REGION_HINTS
from app.modules.agent.services import retrieve
from app.modules.agent.tools.base import (
    Tool,
    ToolContext,
    ToolResult,
    describe,
    recoverable,
    strings,
)
from app.modules.spots import services as spots_services

MIN_SEEDS = 3
SEED_LIMIT = 30
SHOWN = 12
_ANONYMOUS = "로그인하지 않은 사용자입니다. 저장한 곳을 볼 수 없으니 다른 도구로 답하세요."
_ANONYMOUS_FACT = "로그인하면 저장한 곳을 기준으로 추천할 수 있어요. 지금은 그 기준을 쓸 수 없어요."
_TOO_FEW = (
    "저장한 곳이 {count}곳뿐입니다. {need}곳 이상 저장해야 취향을 잡을 수 있으니 "
    "그 사실을 알리고 다른 조건으로 찾아보라고 하세요."
)
_TOO_FEW_FACT = "저장한 곳이 {count}곳이에요. {need}곳 이상 저장하면 취향을 읽어 추천할 수 있어요."
_NO_MATCH = "저장한 곳과 닮은 곳을 찾지 못했습니다."


async def _from_saved(ctx: ToolContext, args: Mapping[str, Any]) -> ToolResult:
    if ctx.user_id is None:
        return ToolResult(rows=[], observation=_ANONYMOUS, fact=_ANONYMOUS_FACT)

    saved, _cursor, _more = await spots_services.list_saved_spots(
        ctx.session, user_id=ctx.user_id, limit=SEED_LIMIT
    )
    seed_ids = await repositories.embedded_ids_among(
        ctx.session, [card.content_id for card in saved]
    )
    if len(seed_ids) < MIN_SEEDS:
        return ToolResult(
            rows=[],
            observation=_TOO_FEW.format(count=len(seed_ids), need=MIN_SEEDS),
            fact=_TOO_FEW_FACT.format(count=len(seed_ids), need=MIN_SEEDS),
        )

    hints = strings(args, "regions", limit=MAX_REGION_HINTS)
    prefixes = await retrieve.resolve_region_prefixes(ctx.session, hints=hints) if hints else []
    matches = await repositories.match_spots_by_centroid(
        ctx.session,
        seed_ids,
        limit=SHOWN,
        region_prefixes=prefixes or None,
    )
    if not matches:
        return ToolResult(rows=[], observation=_NO_MATCH)

    briefs = await repositories.load_candidates_by_ids(
        ctx.session, [match.content_id for match in matches]
    )
    rows: list[CandidateRow] = [
        briefs[match.content_id] for match in matches if match.content_id in briefs
    ]
    titles = {card.content_id: card.title for card in saved}
    seeds = " · ".join(titles[cid] for cid in seed_ids[:3] if cid in titles)
    return ToolResult(
        rows=rows, observation=f"{seeds} 등 저장한 곳 기준 — {describe(rows, empty=_NO_MATCH)}"
    )


FROM_SAVED = Tool(
    name="from_saved",
    description=(
        "사용자가 저장한 곳들의 분위기 평균으로 새 여행지를 찾는다. "
        "'내가 저장한 곳이랑 비슷한 데', '내 취향에 맞는 곳 추천해줘' 같은 질문에 쓴다. "
        "지역을 함께 주면 그 지역 안에서 찾는다."
    ),
    parameters={
        "type": "object",
        "properties": {
            "regions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "찾을 지역. 비우면 전국.",
            }
        },
    },
    label=lambda args: "저장한 곳 기준으로 찾기",
    run=recoverable(_from_saved),
)
