from __future__ import annotations

from typing import Any, ClassVar

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger, get_trace_id
from app.web.envelope import ErrorDetail, err

logger = get_logger(__name__)


class AppError(Exception):
    code: str = "INTERNAL_ERROR"
    http_status: int = 500
    message: str = "Internal server error."
    headers: ClassVar[dict[str, str] | None] = None

    def __init__(
        self,
        message: str | None = None,
        *,
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message or self.message)
        if message:
            self.message = message
        self.details = details or []


class ValidationFailed(AppError):
    code = "VALIDATION_FAILED"
    http_status = 422
    message = "요청 형식이 올바르지 않습니다."


class AuthTokenInvalid(AppError):
    code = "AUTH_TOKEN_INVALID"
    http_status = 401
    message = "유효하지 않은 인증입니다."


class AuthTokenExpired(AppError):
    code = "AUTH_TOKEN_EXPIRED"
    http_status = 401
    message = "인증이 만료되었습니다."


class GuestForbidden(AppError):
    code = "GUEST_FORBIDDEN"
    http_status = 403
    message = "게스트는 사용할 수 없는 기능입니다."


class PermissionDenied(AppError):
    code = "PERMISSION_DENIED"
    http_status = 403
    message = "권한이 없습니다."


class ResourceNotFound(AppError):
    code = "RESOURCE_NOT_FOUND"
    http_status = 404
    message = "요청한 리소스를 찾을 수 없습니다."


class DuplicateResource(AppError):
    code = "DUPLICATE_RESOURCE"
    http_status = 409
    message = "이미 존재하는 리소스입니다."


class ImageInvalid(AppError):
    code = "IMAGE_INVALID"
    http_status = 422
    message = "지원하지 않는 이미지 형식이거나 크기를 초과했습니다."


class RateLimited(AppError):
    code = "RATE_LIMITED"
    http_status = 429
    message = "요청이 너무 잦습니다. 잠시 후 다시 시도해 주세요."


class KtoApiUnavailable(AppError):
    code = "KTO_API_UNAVAILABLE"
    http_status = 502
    message = "한국관광공사 API 응답을 받지 못했습니다."


class LbsConsentRequired(AppError):
    code = "LBS_CONSENT_REQUIRED"
    http_status = 403
    message = "위치 정보 이용 동의가 필요합니다."


class OAuthProviderUnavailable(AppError):
    code = "OAUTH_PROVIDER_UNAVAILABLE"
    http_status = 502
    message = "소셜 로그인 제공자 응답을 받지 못했습니다."


class OAuthIdTokenInvalid(AppError):
    code = "OAUTH_ID_TOKEN_INVALID"
    http_status = 401
    message = "소셜 로그인 토큰이 유효하지 않습니다."


class EmailAlreadyRegistered(AppError):
    code = "EMAIL_TAKEN"
    http_status = 409
    message = "이미 가입된 이메일입니다."


class InvalidCredentials(AppError):
    code = "AUTH_INVALID_CREDENTIALS"
    http_status = 401
    message = "이메일 또는 비밀번호가 올바르지 않습니다."


class AuthSessionRevoked(AppError):
    code = "AUTH_SESSION_REVOKED"
    http_status = 401
    message = "보안상 모든 세션이 종료되었습니다. 다시 로그인해 주세요."


class SessionStoreUnavailable(AppError):
    code = "SESSION_STORE_UNAVAILABLE"
    http_status = 503
    message = "세션 저장소에 일시적인 문제가 발생했습니다."


class AdminUnauthorized(AppError):
    code = "ADMIN_UNAUTHORIZED"
    http_status = 401
    message = "관리자 인증이 필요합니다."


class AdminHistoryNotFound(AppError):
    code = "ADMIN_HISTORY_NOT_FOUND"
    http_status = 404
    message = "해당 날짜의 수집 이력이 없습니다."


class AdminTriggerFailed(AppError):
    code = "ADMIN_TRIGGER_FAILED"
    http_status = 502


class AdminValidationFailed(AppError):
    code = "ADMIN_VALIDATION"
    http_status = 422
    message = "요청이 유효하지 않습니다."


class AdminOverseasNotFound(AppError):
    code = "ADMIN_OVERSEAS_NOT_FOUND"
    http_status = 404
    message = "해당 게시물을 찾을 수 없습니다."


class PlanAgentUnavailable(AppError):
    code = "PLAN_AGENT_UNAVAILABLE"
    http_status = 502
    message = "플랜 서비스를 잠시 사용할 수 없습니다."


class PlanRegionNotFound(AppError):
    code = "PLAN_REGION_NOT_FOUND"
    http_status = 422
    message = "요청한 지역을 찾지 못했습니다."


class PlanNotEnoughSpots(AppError):
    code = "PLAN_NOT_ENOUGH_SPOTS"
    http_status = 422
    message = "해당 지역의 장소 데이터가 부족해 일정을 만들지 못했습니다."


_HTTP_STATUS_TO_CODE = {
    401: "AUTH_TOKEN_INVALID",
    403: "PERMISSION_DENIED",
    404: "RESOURCE_NOT_FOUND",
    405: "RESOURCE_NOT_FOUND",
    429: "RATE_LIMITED",
}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.http_status,
            content=err(
                code=exc.code,
                message=exc.message,
                http_status=exc.http_status,
                details=[ErrorDetail(**d) for d in exc.details],
                trace_id=get_trace_id(),
            ),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            ErrorDetail(
                field=".".join(str(p) for p in e["loc"][1:]) or None,
                issue=e["msg"],
            )
            for e in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=err(
                code="VALIDATION_FAILED",
                message="요청 형식이 올바르지 않습니다.",
                http_status=422,
                details=details,
                trace_id=get_trace_id(),
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _HTTP_STATUS_TO_CODE.get(
            exc.status_code,
            "INTERNAL_ERROR" if exc.status_code >= 500 else "RESOURCE_NOT_FOUND",
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=err(
                code=code,
                message=str(exc.detail),
                http_status=exc.status_code,
                trace_id=get_trace_id(),
            ),
            headers=exc.headers,
        )

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("error.unhandled", error_type=type(exc).__name__)
        return JSONResponse(
            status_code=500,
            content=err(
                code="INTERNAL_ERROR",
                message="서버 오류가 발생했습니다.",
                http_status=500,
                trace_id=get_trace_id(),
            ),
        )
