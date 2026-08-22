from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.modules.agent.errors import AgentOutOfScope
from app.modules.agent.services import retrieve
from app.modules.agent.tools.base import Tool, ToolContext, ToolResult

_NOT_ABROAD = (
    "해외 지명이 없습니다. 이 도구는 대한민국 밖의 여행지에만 씁니다 — "
    "국내 질문이면 다른 도구로 답하세요."
)
_DOMESTIC = "{place} 는 국내 지역입니다. 이 도구를 부르지 말고 국내 검색으로 답하세요."


async def _abroad(ctx: ToolContext, args: Mapping[str, Any]) -> ToolResult:
    """모델 판정을 지역 테이블로 검증한다 — '제주 날씨' 를 해외로 보내고 있었다."""
    place = args.get("place")
    if not isinstance(place, str) or not place.strip():
        return ToolResult(rows=[], observation=_NOT_ABROAD)
    if await retrieve.resolve_region_prefixes(ctx.session, hints=[place.strip()]):
        return ToolResult(rows=[], observation=_DOMESTIC.format(place=place.strip()))
    raise AgentOutOfScope


ABROAD = Tool(
    name="abroad",
    description=(
        "질문에 대한민국 밖의 지명이 나올 때만 부른다. "
        "'파리 가볼 만한 곳', '도쿄 벚꽃 명소', '베트남 여행' 이 그런 질문이다. "
        "국내 지명이거나 지명이 없으면 부르지 않는다 — 길찾기·날씨·항공권처럼 이 앱이 "
        "못 하는 요구라도 국내면 부르지 않는다."
    ),
    parameters={
        "type": "object",
        "properties": {
            "place": {
                "type": "string",
                "description": "질문에 나온 해외 지명 하나. 예: '파리'. 해외 지명이 없으면 부르지 않는다.",
            }
        },
        "required": ["place"],
    },
    label=lambda _args: "해외 여행지 확인",
    run=_abroad,
)
