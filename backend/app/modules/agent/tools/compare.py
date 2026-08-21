from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.modules.agent import repositories
from app.modules.agent.repositories import CandidateRow
from app.modules.agent.schemas import MAX_KEYWORDS, MAX_REGION_HINTS
from app.modules.agent.services import retrieve
from app.modules.agent.tools.base import Tool, ToolContext, ToolResult, recoverable, strings

MAX_REGIONS = 3
TOP_PER_REGION = 6
_TOP_NAMES = 3
_QUIET_RATE = 30
_NEED_TWO = "regions 에 비교할 지역을 둘 이상 넣으세요."


async def _one(ctx: ToolContext, hint: str, keywords: list[str]) -> tuple[str, list[CandidateRow]]:
    prefixes = await retrieve.resolve_region_prefixes(ctx.session, hints=[hint])
    if not prefixes:
        return hint, []
    codes = await retrieve.resolve_category_codes(ctx.session, keywords)
    rows = await retrieve.search_candidates(
        ctx.session,
        repositories.CandidateQuery(
            limit=retrieve.CANDIDATE_LIMIT,
            codes=codes or None,
            region_prefixes=prefixes,
        ),
        preference="any",
        near=False,
    )
    return hint, rows


def _profile(hint: str, rows: Sequence[CandidateRow]) -> str:
    """개수·혼잡도·대표지. 분류 분포는 대부분 attraction 한 덩어리라 쓸모가 없다."""
    if not rows:
        return f"{hint}: 조건에 맞는 곳 없음"
    rated = [row.concentration_rate for row in rows if row.concentration_rate is not None]
    names = " · ".join(row.title for row in rows[:_TOP_NAMES])
    if not rated:
        return f"{hint}: {len(rows)}곳, 혼잡도 자료 없음, 대표 {names}"
    average = round(sum(rated) / len(rated))
    quiet = sum(1 for rate in rated if rate < _QUIET_RATE)
    return (
        f"{hint}: {len(rows)}곳, 평균 혼잡도 {average}"
        f"(한산한 곳 {quiet}/{len(rated)}), 대표 {names}"
    )


async def _compare_regions(ctx: ToolContext, args: Mapping[str, Any]) -> ToolResult:
    hints = strings(args, "regions", limit=MAX_REGION_HINTS)[:MAX_REGIONS]
    if len(hints) < 2:
        return ToolResult(rows=[], observation=_NEED_TWO)

    keywords = strings(args, "categories", limit=MAX_KEYWORDS)
    found = await _sequential(ctx, hints, keywords)
    observation = " | ".join(_profile(hint, rows) for hint, rows in found)

    rows: list[CandidateRow] = []
    for _hint, region_rows in found:
        rows.extend(region_rows[:TOP_PER_REGION])
    return ToolResult(rows=rows, observation=observation)


async def _sequential(
    ctx: ToolContext, hints: list[str], keywords: list[str]
) -> list[tuple[str, list[CandidateRow]]]:
    """한 세션을 공유하므로 순차로 돈다 — asyncpg 는 동시 사용을 거부한다."""
    return [await _one(ctx, hint, keywords) for hint in hints]


COMPARE_REGIONS = Tool(
    name="compare_regions",
    description=(
        "두세 지역을 나란히 놓고 견준다. '부산이랑 여수 중 어디가 나아?' 같은 질문에 쓴다. "
        "각 지역의 스팟 수·분류 분포·대표 장소를 함께 돌려준다. "
        "한 지역만 물으면 category_search 를 쓴다."
    ),
    parameters={
        "type": "object",
        "properties": {
            "regions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "견줄 지역 이름 둘 이상. 예: ['부산','여수'].",
            },
            "categories": {
                "type": "array",
                "items": {"type": "string"},
                "description": "견줄 기준이 되는 장소 종류. 비우면 전체.",
            },
        },
        "required": ["regions"],
    },
    label=lambda args: " vs ".join(strings(args, "regions", limit=MAX_REGIONS)) + " 비교",
    run=recoverable(_compare_regions),
)
