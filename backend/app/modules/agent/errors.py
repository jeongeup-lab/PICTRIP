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


class AgentFestivalUnavailable(AppError):
    code = "AGENT_FESTIVAL_UNAVAILABLE"
    http_status = 422
    message = "축제 정보를 가져오지 못했어요. 잠시 후 다시 시도해 주세요."


class AgentWriterUnavailable(AppError):
    code = "AGENT_WRITER_UNAVAILABLE"
    http_status = 502
    message = "답변을 쓰다가 끊겼어요. 잠시 후 다시 시도해 주세요."


class AgentOutOfScope(AppError):
    code = "AGENT_OUT_OF_SCOPE"
    http_status = 422
    message = "그건 제가 도와드릴 수 없어요. 국내 여행지를 지역이나 분위기로 물어봐 주세요."
