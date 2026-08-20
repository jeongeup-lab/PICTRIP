from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.modules.agent import repositories
from app.modules.agent.repositories import CandidateRow
from app.modules.agent.services import anchor as anchor_service
from app.modules.agent.services import retrieve
from app.modules.agent.tools.base import (
    Tool,
    ToolContext,
    ToolResult,
    describe,
    recoverable,
)
from app.modules.spots.services import find_nearby_spots

_NO_ANCHOR = "contentId 가 없습니다. 먼저 검색해 스팟을 고르세요."
_UNKNOWN = "그 contentId 로 스팟을 찾지 못했습니다."
_KINDS = tuple(anchor_service.ANCHOR_CATEGORIES)

_ANCHOR_PARAMS = {
    "type": "object",
    "properties": {"contentId": {"type": "string", "description": "기준이 되는 스팟의 contentId."}},
    "required": ["contentId"],
}


async def _load(ctx: ToolContext, args: Mapping[str, Any]) -> CandidateRow | None:
    content_id = args.get("contentId")
    if not isinstance(content_id, str) or not content_id:
        return None
    briefs = await repositories.load_candidates_by_ids(ctx.session, [content_id])
    return briefs.get(content_id)


def _rows_in(briefs: Mapping[str, CandidateRow], ids: Sequence[str]) -> list[CandidateRow]:
    return [briefs[cid] for cid in ids if cid in briefs]


async def _nearby(ctx: ToolContext, args: Mapping[str, Any]) -> ToolResult:
    kind = args.get("kind")
    if kind not in _KINDS:
        kind = "nearby"
    row = await _load(ctx, args)
    lat = row.lat if row is not None else ctx.lat
    lng = row.lng if row is not None else ctx.lng
    if lat is None or lng is None:
        return ToolResult(rows=[], observation=_NO_ANCHOR if row is None else _UNKNOWN)

    found = await find_nearby_spots(
        ctx.session,
        lat=lat,
        lng=lng,
        radius=anchor_service.ANCHOR_RADIUS_M,
        category=anchor_service.ANCHOR_CATEGORIES[kind],
        travel_only=kind == "nearby",
    )
    kept = [near for near in found if row is None or near.content_id != row.content_id]
    kept = kept[: retrieve.RESULT_LIMIT]
    briefs = await repositories.load_candidates_by_ids(
        ctx.session, [near.content_id for near in kept]
    )
    rows = _rows_in(briefs, [near.content_id for near in kept])
    return ToolResult(
        rows=rows,
        observation=describe(rows, empty="반경 3km 안에 없습니다. 다른 기준점을 쓰세요."),
    )


async def _related(ctx: ToolContext, args: Mapping[str, Any]) -> ToolResult:
    row = await _load(ctx, args)
    if row is None:
        return ToolResult(rows=[], observation=_NO_ANCHOR)
    vector = await repositories.load_spot_embedding(ctx.session, row.content_id)
    if vector is None:
        return ToolResult(rows=[], observation=f"{row.title} 은 임베딩이 없어 연관을 못 냅니다.")

    matches = await repositories.match_spots_by_vector(
        ctx.session, vector, limit=retrieve.RESULT_LIMIT + 1
    )
    ids = [match.content_id for match in matches if match.content_id != row.content_id]
    ids = ids[: retrieve.RESULT_LIMIT]
    briefs = await repositories.load_candidates_by_ids(ctx.session, ids)
    rows = _rows_in(briefs, ids)
    return ToolResult(rows=rows, observation=describe(rows, empty="연관 관광지가 없습니다."))


async def _concentration(ctx: ToolContext, args: Mapping[str, Any]) -> ToolResult:
    row = await _load(ctx, args)
    if row is None:
        return ToolResult(rows=[], observation=_NO_ANCHOR)
    if row.concentration_rate is None:
        return ToolResult(rows=[row], observation=f"{row.title} 은 혼잡도 자료가 없습니다.")
    return ToolResult(
        rows=[row],
        observation=f"{row.title} 혼잡도 {round(row.concentration_rate)}점 (0~100, 높을수록 붐빔)",
    )


NEARBY = Tool(
    name="nearby",
    description=(
        "기준 스팟 반경 3km 안의 볼거리·맛집·카페를 찾는다. "
        "'거기 근처', '그 주변' 같은 요청에 쓴다. contentId 는 직전 결과에서 고른다."
    ),
    parameters={
        "type": "object",
        "properties": {
            "contentId": {
                "type": "string",
                "description": "기준 스팟. 없으면 사용자 현재 위치를 쓴다.",
            },
            "kind": {
                "type": "string",
                "enum": list(_KINDS),
                "description": "찾을 종류. 기본은 nearby(볼거리).",
            },
        },
    },
    label=lambda args: (
        f"주변 {anchor_service.ANCHOR_NOUNS.get(str(args.get('kind')), '볼거리')} 조회"
    ),
    run=recoverable(_nearby),
)

RELATED = Tool(
    name="related",
    description="기준 스팟과 사진이 닮은 국내 여행지를 임베딩 이웃으로 찾는다.",
    parameters=_ANCHOR_PARAMS,
    label=lambda _args: "연관 관광지 조회",
    run=recoverable(_related),
)

CONCENTRATION = Tool(
    name="concentration",
    description="특정 스팟 한 곳의 혼잡도를 조회한다. 여러 곳을 거르는 용도가 아니다.",
    parameters=_ANCHOR_PARAMS,
    label=lambda _args: "혼잡도 조회",
    run=recoverable(_concentration),
)
