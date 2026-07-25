from __future__ import annotations

from app.web.errors import AppError


class AgentIntentUnavailable(AppError):
    code = "AGENT_INTENT_UNAVAILABLE"
    http_status = 502
    message = "질문을 이해하는 데 실패했어요. 잠시 후 다시 시도해 주세요."


class AgentNoResults(AppError):
    code = "AGENT_NO_RESULTS"
    http_status = 422
    message = "조건에 맞는 곳을 찾지 못했어요. 조건을 조금 넓혀 보세요."
