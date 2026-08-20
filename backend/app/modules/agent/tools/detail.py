from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast, get_args

from app.modules.agent import repositories
from app.modules.agent.schemas import MAX_DETAIL_FIELDS, DetailField
from app.modules.agent.services import detail as detail_service
from app.modules.agent.tools.base import (
    Tool,
    ToolContext,
    ToolResult,
    recoverable,
    strings,
)
from app.modules.spots.services import load_spot_detail

_FIELDS = list(get_args(DetailField))
_DEFAULTS: tuple[DetailField, ...] = ("hours", "closed")
_STALE = "KTO 상세를 아직 못 받아왔습니다. 다른 곳으로 답하세요."


def _asked(args: Mapping[str, Any]) -> list[DetailField]:
    picked = [
        cast(DetailField, name)
        for name in strings(args, "fields", limit=MAX_DETAIL_FIELDS)
        if name in _FIELDS
    ]
    return picked or list(_DEFAULTS)


async def _spot_detail(ctx: ToolContext, args: Mapping[str, Any]) -> ToolResult:
    content_id = args.get("contentId")
    if not isinstance(content_id, str) or not content_id:
        return ToolResult(rows=[], observation="contentId 가 비었습니다.")

    fields = _asked(args)
    row = await load_spot_detail(
        ctx.session,
        ctx.kto,  # type: ignore[arg-type]
        ctx.redis,
        content_id,
        defer_refresh=ctx.kto is None,
        require_intro=any(field != "overview" for field in fields),
    )
    briefs = await repositories.load_candidates_by_ids(ctx.session, [content_id])
    rows = [briefs[content_id]] if content_id in briefs else []

    if row.detail_status in ("pending", "unavailable"):
        return ToolResult(rows=[], anchors=rows, observation=f"{row.title}: {_STALE}")

    known = [
        f"{detail_service.FIELD_NOUNS[field]} {value}"
        for field in fields
        if (value := _value(row, field))
    ]
    if not known:
        nouns = " · ".join(detail_service.FIELD_NOUNS[field] for field in fields)
        return ToolResult(
            rows=[], anchors=rows, observation=f"{row.title}: {nouns} 자료가 없습니다."
        )
    return ToolResult(rows=[], anchors=rows, observation=f"{row.title} — " + " · ".join(known))


def _value(row: Any, field: DetailField) -> str | None:
    if field == "overview":
        overview: str | None = row.overview
        return overview[:200] if overview else None
    return detail_service.field_value(row.intro, row.tel, field)


SPOT_DETAIL = Tool(
    name="spot_detail",
    description=(
        "한 곳의 이용시간·쉬는 날·주차·문의·요금·소개를 조회한다. "
        "'거기 몇 시에 열어?', '월요일에 가도 돼?' 같은 질문에 쓴다. "
        "여러 곳을 거르는 용도가 아니다 — contentId 는 직전 결과에서 고른다."
    ),
    parameters={
        "type": "object",
        "properties": {
            "contentId": {"type": "string", "description": "조회할 스팟의 contentId."},
            "fields": {
                "type": "array",
                "items": {"type": "string", "enum": _FIELDS},
                "description": "물어본 항목만. 비우면 이용시간과 쉬는 날.",
            },
        },
        "required": ["contentId"],
    },
    label=lambda _args: "상세 조회",
    run=recoverable(_spot_detail),
    carries_facts=True,
)
