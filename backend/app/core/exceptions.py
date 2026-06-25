"""Application error taxonomy aligned with API spec §4-2 envelope error codes."""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Base for all application errors. Mapped to envelope `error.code`."""

    code: str = "INTERNAL_ERROR"
    http_status: int = 500
    message: str = "Internal server error."

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


class Max5Moods(AppError):
    code = "MAX_5_MOODS"
    http_status = 422
    message = "관심 무드는 최대 5개까지 선택할 수 있습니다."


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


class LlmApiUnavailable(AppError):
    code = "LLM_API_UNAVAILABLE"
    http_status = 502
    message = "추천 설명을 생성하지 못했습니다. 잠시 후 다시 시도해 주세요."


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


# --- admin console (A01 §3) — kept here so the admin/ skeleton compiles ---
class AdminUnauthorized(AppError):
    code = "ADMIN_UNAUTHORIZED"
    http_status = 401


class AdminHistoryNotFound(AppError):
    code = "ADMIN_HISTORY_NOT_FOUND"
    http_status = 404


class AdminTriggerFailed(AppError):  # Phase 2
    code = "ADMIN_TRIGGER_FAILED"
    http_status = 502
