from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast, get_args

from app.modules.agent import repositories
from app.modules.agent.schemas import (
    MAX_KEYWORDS,
    MAX_MOOD_HINTS,
    MAX_REGION_HINTS,
    CrowdPreference,
    Mood,
)
from app.modules.agent.services import retrieve
from app.modules.agent.services import scene as scene_service
from app.modules.agent.tools.base import Tool, ToolContext, ToolResult, describe, strings

_NO_MATCH = "결과 0곳. 조건을 줄이거나 지역을 넓혀 다시 부르세요."

_REGION_HINTS = {
    "type": "array",
    "items": {"type": "string"},
    "description": "시도·시군구 이름. 예: ['통영'], ['제주특별자치도']. 전국이면 비운다.",
}


_MOODS = list(get_args(Mood))


def _moods(args: Mapping[str, Any]) -> list[str]:
    picked = strings(args, "moods", limit=MAX_MOOD_HINTS)
    return [mood for mood in picked if mood in _MOODS]


def _crowd(args: Mapping[str, Any]) -> CrowdPreference:
    value = args.get("crowd")
    return cast(CrowdPreference, value) if value in ("quiet", "any", "popular") else "any"


async def _category_search(ctx: ToolContext, args: Mapping[str, Any]) -> ToolResult:
    keywords = strings(args, "categories", limit=MAX_KEYWORDS)
    hints = strings(args, "regions", limit=MAX_REGION_HINTS)
    near = bool(args.get("near")) and ctx.lat is not None and ctx.lng is not None

    codes = await retrieve.resolve_category_codes(ctx.session, keywords)
    prefixes = await retrieve.resolve_region_prefixes(ctx.session, hints=hints)
    mood_ids = await repositories.find_mood_ids(ctx.session, _moods(args))
    rows = await retrieve.search_candidates(
        ctx.session,
        repositories.CandidateQuery(
            limit=retrieve.CANDIDATE_LIMIT,
            codes=codes or None,
            region_prefixes=prefixes or None,
            lat=ctx.lat,
            lng=ctx.lng,
            indoor_only=bool(args.get("indoor")),
            mood_ids=mood_ids,
        ),
        preference=_crowd(args),
        near=near,
    )
    return ToolResult(rows=rows, observation=describe(rows, empty=_NO_MATCH))


async def _title_search(ctx: ToolContext, args: Mapping[str, Any]) -> ToolResult:
    keywords = strings(args, "keywords", limit=MAX_KEYWORDS)
    if not keywords:
        return ToolResult(rows=[], observation="keywords 가 비었습니다.")
    prefixes = await retrieve.resolve_region_prefixes(
        ctx.session, hints=strings(args, "regions", limit=MAX_REGION_HINTS)
    )
    rows = await retrieve.search_by_title(ctx.session, keywords, region_prefixes=prefixes)
    return ToolResult(rows=rows, observation=describe(rows, empty=_NO_MATCH))


async def _photo_match(ctx: ToolContext, args: Mapping[str, Any]) -> ToolResult:
    term = args.get("scene")
    if not isinstance(term, str) or not term:
        return ToolResult(rows=[], observation="scene 이 비었습니다.")
    prefixes = await retrieve.resolve_region_prefixes(
        ctx.session, hints=strings(args, "regions", limit=MAX_REGION_HINTS)
    )
    rows = await scene_service.search(ctx.session, term, region_prefixes=prefixes)
    return ToolResult(rows=rows, observation=describe(rows, empty=_NO_MATCH))


CATEGORY_SEARCH = Tool(
    name="category_search",
    description=(
        "지역·카테고리·분위기로 국내 여행지를 찾는다. 가장 기본이 되는 검색이다. "
        "결과가 0곳이면 지역을 넓히거나 카테고리를 지워 다시 부를 수 있다."
    ),
    parameters={
        "type": "object",
        "properties": {
            "regions": _REGION_HINTS,
            "categories": {
                "type": "array",
                "items": {"type": "string"},
                "description": "카테고리 낱말. 예: ['카페'], ['박물관','미술관'].",
            },
            "crowd": {
                "type": "string",
                "enum": ["quiet", "any", "popular"],
                "description": "혼잡도 선호. 한적하면 quiet, 유명한 곳이면 popular.",
            },
            "moods": {
                "type": "array",
                "items": {"type": "string", "enum": _MOODS},
                "description": "분위기 축. 카테고리와 함께 쓰면 결과를 좁힌다.",
            },
            "indoor": {"type": "boolean", "description": "실내만 고를지."},
            "near": {"type": "boolean", "description": "사용자 좌표 기준 거리순으로 볼지."},
        },
    },
    label=lambda args: _category_label(args),
    run=_category_search,
)

TITLE_SEARCH = Tool(
    name="title_search",
    description="이름에 특정 낱말이 든 여행지를 찾는다. 예: '케이블카', '출렁다리'.",
    parameters={
        "type": "object",
        "properties": {
            "keywords": {
                "type": "array",
                "items": {"type": "string"},
                "description": "이름에 들어갈 낱말.",
            },
            "regions": _REGION_HINTS,
        },
        "required": ["keywords"],
    },
    label=lambda args: f"{_first(args, 'keywords')} 이름으로 조회",
    run=_title_search,
)

PHOTO_MATCH = Tool(
    name="photo_match",
    description="장면 문구를 임베딩해 사진이 닮은 곳을 찾는다. 분위기 묘사에 쓴다.",
    parameters={
        "type": "object",
        "properties": {
            "scene": {"type": "string", "description": "장면 문구. 예: '노을 지는 바닷가'."},
            "regions": _REGION_HINTS,
        },
        "required": ["scene"],
    },
    label=lambda args: f"{args.get('scene', '사진')} 사진으로 찾기",
    run=_photo_match,
)


def _first(args: Mapping[str, Any], key: str) -> str:
    values = strings(args, key, limit=1)
    return values[0] if values else "이름"


def _category_label(args: Mapping[str, Any]) -> str:
    if args.get("indoor"):
        head = "실내"
    elif categories := strings(args, "categories", limit=2):
        head = " · ".join(categories)
    elif regions := strings(args, "regions", limit=1):
        head = regions[0]
    else:
        head = "전국"
    return f"{head} 관광지 조회"
