from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.modules.agent import repositories
from app.modules.agent.schemas import MAX_REGION_HINTS
from app.modules.agent.services import photo as photo_service
from app.modules.agent.services import retrieve
from app.modules.agent.tools.base import (
    Tool,
    ToolContext,
    ToolResult,
    describe,
    recoverable,
    strings,
)

_NO_PHOTO = "사용자가 사진을 첨부하지 않았습니다. 다른 도구를 쓰세요."
_NO_MATCH = "사진과 닮은 곳을 찾지 못했습니다. 지역을 넓혀 다시 부르세요."


async def _uploaded_photo(ctx: ToolContext, args: Mapping[str, Any]) -> ToolResult:
    if not ctx.image_bytes:
        return ToolResult(rows=[], observation=_NO_PHOTO)

    hints = strings(args, "regions", limit=MAX_REGION_HINTS)
    prefixes = await retrieve.resolve_region_prefixes(ctx.session, hints=hints) if hints else []
    vector = await photo_service.embed_photo(image_bytes=ctx.image_bytes, image_mime=ctx.image_mime)
    matched = await photo_service.match_vector(ctx.session, vector, region_prefixes=prefixes)
    ids = [row.content_id for row in matched]
    briefs = await repositories.load_candidates_by_ids(ctx.session, ids)
    rows = [briefs[cid] for cid in ids if cid in briefs]
    return ToolResult(rows=rows, observation=describe(rows, empty=_NO_MATCH))


UPLOADED_PHOTO = Tool(
    name="uploaded_photo",
    description=(
        "사용자가 첨부한 사진과 분위기가 닮은 국내 여행지를 찾는다. "
        "사진이 붙은 질문에만 쓴다. 계절·현상 낱말로 찾을 때는 photo_match 를 쓴다."
    ),
    parameters={
        "type": "object",
        "properties": {
            "regions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "좁힐 지역. 비우면 전국.",
            }
        },
    },
    label=lambda _args: "사진과 닮은 곳 찾기",
    run=recoverable(_uploaded_photo),
)
