from __future__ import annotations

from app.web.errors import AppError


class PlanSourceInvalid(AppError):
    code = "PLAN_SOURCE_INVALID"
    http_status = 422
    message = "지원하지 않는 입력입니다. 스크린샷·텍스트·유튜브 링크를 보내주세요."


class PlanTranscriptUnavailable(AppError):
    code = "PLAN_TRANSCRIPT_UNAVAILABLE"
    http_status = 422
    message = "이 영상에서는 자막을 가져올 수 없습니다. 다른 영상이나 텍스트로 시도해 주세요."


class PlanNoPlacesFound(AppError):
    code = "PLAN_NO_PLACES_FOUND"
    http_status = 422
    message = "콘텐츠에서 장소 이름을 찾지 못했습니다. 장소명이 나오는 콘텐츠를 보내주세요."


class PlanLlmUnavailable(AppError):
    code = "PLAN_LLM_UNAVAILABLE"
    http_status = 502
    message = "장소 추출 서비스가 일시적으로 응답하지 않습니다."


class PlanLlmBusy(AppError):
    code = "PLAN_LLM_BUSY"
    http_status = 429
    message = "추출 요청이 몰려 있습니다. 1분쯤 후 다시 시도해 주세요."


class PlanNotFound(AppError):
    code = "PLAN_NOT_FOUND"
    http_status = 404
    message = "요청한 일정을 찾을 수 없습니다."
