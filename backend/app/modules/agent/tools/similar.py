from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.modules.agent import repositories
from app.modules.agent.repositories import CandidateRow
from app.modules.agent.schemas import MAX_REGION_HINTS
from app.modules.agent.services import retrieve
from app.modules.agent.tools.base import Tool, ToolContext, ToolResult, recoverable, strings

SEEDS = 5
NEIGHBOURS = 12
TOP_REGIONS = 3
SHOWN = 9
_UNKNOWN = "그 이름을 지역으로 해석하지 못했습니다. 시도·시군구 이름으로 다시 부르세요."
_NO_SEED = "그 지역에는 사진 임베딩이 있는 곳이 없어 분위기를 견줄 수 없습니다."
_NO_MATCH = "다른 지역에서 닮은 곳을 찾지 못했습니다."


def _sido(row: CandidateRow) -> str | None:
    """지역 코드 조인이 비는 스팟이 있어 주소를 먼저 본다."""
    if row.addr1:
        head = row.addr1.split(" ", 1)[0]
        if head:
            return head
    return row.region_name


async def _similar_region(ctx: ToolContext, args: Mapping[str, Any]) -> ToolResult:
    hints = strings(args, "regions", limit=MAX_REGION_HINTS)
    if not hints:
        return ToolResult(rows=[], observation="regions 가 비었습니다.")

    prefixes = await retrieve.resolve_region_prefixes(ctx.session, hints=hints)
    if not prefixes:
        return ToolResult(rows=[], observation=f"{hints[0]}: {_UNKNOWN}")

    seed_ids = await repositories.embedded_spot_ids(
        ctx.session, region_prefixes=prefixes, limit=SEEDS
    )
    if not seed_ids:
        return ToolResult(rows=[], observation=f"{hints[0]}: {_NO_SEED}")

    briefs = await repositories.load_candidates_by_ids(ctx.session, seed_ids)
    seeds = [briefs[cid] for cid in seed_ids if cid in briefs]
    source = {_sido(row) for row in seeds if _sido(row)}
    found = await _vote(ctx, seeds, source)
    if not found:
        return ToolResult(rows=[], observation=f"{hints[0]}: {_NO_MATCH}")

    tally: dict[str, list[CandidateRow]] = {}
    for row in found:
        name = _sido(row)
        if name:
            tally.setdefault(name, []).append(row)
    ranked = sorted(tally.items(), key=lambda pair: -len(pair[1]))[:TOP_REGIONS]

    summary = " · ".join(f"{name} {len(rows)}곳({rows[0].title})" for name, rows in ranked)
    picked = [row for _name, rows in ranked for row in rows[:TOP_REGIONS]][:SHOWN]
    return ToolResult(rows=picked, observation=f"{hints[0]} 와 분위기가 닮은 지역: {summary}")


async def _vote(
    ctx: ToolContext, seeds: list[CandidateRow], source: set[str | None]
) -> list[CandidateRow]:
    """씨앗마다 이웃을 뽑아 다른 지역 쪽만 남긴다 — 한 세션이라 순차로 돈다."""
    picked: dict[str, CandidateRow] = {}
    for seed in seeds:
        vector = await repositories.load_spot_embedding(ctx.session, seed.content_id)
        if vector is None:
            continue
        matches = await repositories.match_spots_by_vector(ctx.session, vector, limit=NEIGHBOURS)
        ids = [match.content_id for match in matches]
        briefs = await repositories.load_candidates_by_ids(ctx.session, ids)
        for content_id in ids:
            row = briefs.get(content_id)
            if row is None or _sido(row) in source or content_id in picked:
                continue
            picked[content_id] = row
    return list(picked.values())


SIMILAR_REGION = Tool(
    name="similar_region",
    description=(
        "한 지역과 사진 분위기가 닮은 다른 지역을 찾는다. "
        "'제주 같은 분위기인데 육지에서', '여수랑 비슷한 데' 같은 질문에 쓴다. "
        "같은 지역 안에서 찾는 게 아니라 다른 시도를 골라 준다."
    ),
    parameters={
        "type": "object",
        "properties": {
            "regions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "기준이 되는 지역 이름 하나. 예: ['제주'].",
            }
        },
        "required": ["regions"],
    },
    label=lambda args: f"{(strings(args, 'regions', limit=1) or ['지역'])[0]} 와 닮은 지역 찾기",
    run=recoverable(_similar_region),
)
