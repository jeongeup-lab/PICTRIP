from __future__ import annotations

from typing import Any

from app.modules.agent.schemas import ToolName
from app.modules.agent.tools.anchored import CONCENTRATION, NEARBY, RELATED
from app.modules.agent.tools.base import Tool
from app.modules.agent.tools.compare import COMPARE_REGIONS
from app.modules.agent.tools.detail import SPOT_DETAIL
from app.modules.agent.tools.festival import FESTIVAL
from app.modules.agent.tools.itinerary import PLAN_ITINERARY
from app.modules.agent.tools.photo import UPLOADED_PHOTO
from app.modules.agent.tools.profile import REGION_PROFILE
from app.modules.agent.tools.resolve import RESOLVE_PLACE
from app.modules.agent.tools.search import CATEGORY_SEARCH, PHOTO_MATCH, TITLE_SEARCH
from app.modules.agent.tools.similar import SIMILAR_REGION

_TOOLS: tuple[Tool, ...] = (
    CATEGORY_SEARCH,
    TITLE_SEARCH,
    COMPARE_REGIONS,
    REGION_PROFILE,
    PLAN_ITINERARY,
    SIMILAR_REGION,
    RESOLVE_PLACE,
    SPOT_DETAIL,
    FESTIVAL,
    PHOTO_MATCH,
    UPLOADED_PHOTO,
    NEARBY,
    RELATED,
    CONCENTRATION,
)

CATALOG: dict[ToolName, Tool] = {tool.name: tool for tool in _TOOLS}


def schemas() -> list[dict[str, Any]]:
    """프로바이더 tool-calling 에 그대로 넘길 함수 선언."""
    return [
        {"name": tool.name, "description": tool.description, "parameters": tool.parameters}
        for tool in _TOOLS
    ]
