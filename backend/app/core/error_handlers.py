"""FastAPI exception handlers that wrap responses in the standard envelope."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import AppError
from app.core.logging import get_logger, get_trace_id
from app.core.schemas import ErrorDetail, err

logger = get_logger(__name__)

# Starlette raises HTTPException for routing-level failures that never pass
# through the AppError taxonomy (no matching route → 404, wrong method → 405,
# …). Map those onto taxonomy codes so the mobile client only ever sees codes
# it can branch on per the {data,error,meta} contract — `code="HTTP_ERROR"`
# was not a member of the taxonomy. Unmapped statuses collapse to
# INTERNAL_ERROR (5xx) or RESOURCE_NOT_FOUND (other 4xx).
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
            # Forward any auth challenge etc. (e.g. WWW-Authenticate: Basic from
            # AdminUnauthorized), mirroring the HTTPException handler below.
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
            # Preserve auth challenges etc. (e.g. WWW-Authenticate: Basic from
            # the admin Basic-auth gate) that the raiser attached to the exception.
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
