from __future__ import annotations

from typing import Any

from app.modules.agent.schemas import ToolName
from app.modules.agent.tools.anchored import CONCENTRATION, NEARBY, RELATED
from app.modules.agent.tools.base import Tool
from app.modules.agent.tools.search import CATEGORY_SEARCH, PHOTO_MATCH, TITLE_SEARCH

_TOOLS: tuple[Tool, ...] = (
    CATEGORY_SEARCH,
    TITLE_SEARCH,
    PHOTO_MATCH,
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
