from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.modules.agent import repositories
from app.modules.agent.repositories import CandidateRow
from app.modules.agent.schemas import MAX_REGION_HINTS
from app.modules.agent.services import retrieve
from app.modules.agent.tools.base import Tool, ToolContext, ToolResult, recoverable, strings

TOP_DISTRICTS = 3
TOP_NAMES = 5
SHOWN = 8
_QUIET_RATE = 30
_UNKNOWN = "그 이름을 지역으로 해석하지 못했습니다. 시도·시군구 이름으로 다시 부르세요."
_EMPTY = "그 지역에는 잡히는 관광지가 없습니다."


def _districts(rows: Sequence[CandidateRow]) -> str:
    counts: dict[str, int] = {}
    for row in rows:
        if row.sigungu_name:
            counts[row.sigungu_name] = counts.get(row.sigungu_name, 0) + 1
    top = sorted(counts.items(), key=lambda pair: -pair[1])[:TOP_DISTRICTS]
    if len(counts) < 2:
        return ""
    return " · ".join(f"{name} {count}" for name, count in top)


def _crowd(rows: Sequence[CandidateRow]) -> str:
    rated = [row.concentration_rate for row in rows if row.concentration_rate is not None]
    if not rated:
        return "혼잡도 자료 없음"
    average = round(sum(rated) / len(rated))
    quiet = sum(1 for rate in rated if rate < _QUIET_RATE)
    return f"평균 혼잡도 {average}, 한산한 곳 {quiet}/{len(rated)}"


async def _region_profile(ctx: ToolContext, args: Mapping[str, Any]) -> ToolResult:
    hints = strings(args, "regions", limit=MAX_REGION_HINTS)
    if not hints:
        return ToolResult(rows=[], observation="regions 가 비었습니다.")

    prefixes = await retrieve.resolve_region_prefixes(ctx.session, hints=hints)
    if not prefixes:
        return ToolResult(rows=[], observation=f"{hints[0]}: {_UNKNOWN}")

    rows = await retrieve.search_candidates(
        ctx.session,
        repositories.CandidateQuery(limit=retrieve.CANDIDATE_LIMIT, region_prefixes=prefixes),
        preference="any",
        near=False,
    )
    if not rows:
        return ToolResult(rows=[], observation=f"{hints[0]}: {_EMPTY}")

    indoor = sum(1 for row in rows if row.indoor)
    parts = [f"{hints[0]}: 관광지 {len(rows)}곳", _crowd(rows)]
    if districts := _districts(rows):
        parts.append(f"많은 곳 {districts}")
    parts.append(f"실내 {indoor}곳")
    parts.append("대표 " + " · ".join(row.title for row in rows[:TOP_NAMES]))
    return ToolResult(rows=rows[:SHOWN], observation=", ".join(parts))


REGION_PROFILE = Tool(
    name="region_profile",
    description=(
        "한 지역이 어떤 곳인지 요약한다. '전주는 어떤 도시야?', '제주 어때?' 같은 질문에 쓴다. "
        "관광지 수·혼잡도·많이 몰린 시군구·실내 비율·대표 장소를 함께 돌려준다. "
        "특정 종류를 찾는 질문에는 category_search 를 쓴다."
    ),
    parameters={
        "type": "object",
        "properties": {
            "regions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "요약할 지역 이름 하나. 예: ['전주'].",
            }
        },
        "required": ["regions"],
    },
    label=lambda args: f"{(strings(args, 'regions', limit=1) or ['지역'])[0]} 살펴보기",
    run=recoverable(_region_profile),
)
