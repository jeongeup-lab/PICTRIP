from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.modules.agent import repositories
from app.modules.agent.schemas import MAX_NAMED_PLACES, ExtractedPlace, PlaceType
from app.modules.agent.services import resolve as resolve_service
from app.modules.agent.tools.base import (
    Tool,
    ToolContext,
    ToolResult,
    describe,
    recoverable,
    strings,
)

_PLACE_TYPES: tuple[PlaceType, ...] = ("attraction", "restaurant", "cafe", "hotel", "region")
_NOT_FOUND = "그 이름으로 국내 관광지를 찾지 못했습니다. 일반 검색으로 넘어가세요."
_NOT_A_NAME = "장소 이름이 아닙니다. 숫자나 기호만으로는 장소를 찾을 수 없습니다."


def _extracted(args: Mapping[str, Any]) -> list[ExtractedPlace]:
    kind = args.get("placeType")
    place_type: PlaceType = kind if kind in _PLACE_TYPES else "attraction"
    hint = args.get("regionHint")
    return [
        ExtractedPlace(
            name=name,
            placeType=place_type,
            regionHint=hint if isinstance(hint, str) and hint else None,
        )
        for name in strings(args, "names", limit=MAX_NAMED_PLACES)
    ]


def _named(places: list[ExtractedPlace]) -> list[ExtractedPlace]:
    """'12345' 를 장소로 해석해 상세까지 조회했다 — 이름에 글자가 하나는 있어야 한다."""
    return [place for place in places if any(char.isalpha() for char in place.name)]


async def _resolve_place(ctx: ToolContext, args: Mapping[str, Any]) -> ToolResult:
    places = _extracted(args)
    if not places:
        return ToolResult(rows=[], observation="names 가 비었습니다.")
    places = _named(places)
    if not places:
        return ToolResult(rows=[], observation=_NOT_A_NAME, stop=True)

    resolved = await resolve_service.resolve_places(ctx.session, ctx.kto, places)
    content_ids = [
        place.spot.contentId
        for place in resolved
        if place.spot is not None and place.spot.contentId
    ]
    briefs = await repositories.load_candidates_by_ids(ctx.session, content_ids)
    rows = [briefs[cid] for cid in content_ids if cid in briefs]
    if rows:
        return ToolResult(rows=rows, observation=describe(rows, empty=_NOT_FOUND))

    named = [place.extracted.name for place in resolved]
    return ToolResult(rows=[], observation=f"{' · '.join(named)}: {_NOT_FOUND}")


RESOLVE_PLACE = Tool(
    name="resolve_place",
    description=(
        "질문이 특정 장소를 이름으로 지목할 때 그 한 곳을 집는다. "
        "예: '감천문화마을', '대천역'. 일반명사(폭포·박물관)나 지역명(세종·부산)에는 쓰지 않는다. "
        "그 장소 자체를 물으면 이 도구를, 그 주변을 물으면 이걸로 집은 뒤 nearby 를 쓴다."
    ),
    parameters={
        "type": "object",
        "properties": {
            "names": {
                "type": "array",
                "items": {"type": "string"},
                "description": "지목된 장소 이름 그대로.",
            },
            "placeType": {
                "type": "string",
                "enum": list(_PLACE_TYPES),
                "description": "장소 갈래. 기본은 attraction.",
            },
            "regionHint": {"type": "string", "description": "같은 이름이 여럿일 때 좁힐 지역."},
        },
        "required": ["names"],
    },
    label=lambda args: "질문 속 장소 확인",
    run=recoverable(_resolve_place),
)
