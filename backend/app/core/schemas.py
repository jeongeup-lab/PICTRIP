"""Common response envelope schemas matching API spec §1-4."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

DataT = TypeVar("DataT")


def _now_utc() -> datetime:
    return datetime.now(tz=UTC)


class ErrorDetail(BaseModel):
    field: str | None = None
    issue: str


class ErrorPayload(BaseModel):
    code: str
    message: str
    details: list[ErrorDetail] = Field(default_factory=list)
    traceId: str | None = None


class PaginationMeta(BaseModel):
    nextCursor: str | None = None
    hasMore: bool = False
    count: int = 0


class ResponseMeta(BaseModel):
    traceId: str | None = None
    requestedAt: datetime = Field(default_factory=_now_utc)
    pagination: PaginationMeta | None = None


class Envelope(BaseModel, Generic[DataT]):
    """Standard response envelope: { data, error, meta }."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    data: DataT | None = None
    error: ErrorPayload | None = None
    meta: ResponseMeta = Field(default_factory=ResponseMeta)


def _resolve_trace_id(explicit: str | None) -> str | None:
    if explicit is not None:
        return explicit
    # Lazy import to avoid circular dependency: logging -> nothing, schemas -> logging.
    from app.core.logging import get_trace_id

    return get_trace_id()


def ok(
    data: Any,
    *,
    trace_id: str | None = None,
    pagination: PaginationMeta | None = None,
) -> dict[str, Any]:
    resolved = _resolve_trace_id(trace_id)
    return Envelope[Any](
        data=data,
        meta=ResponseMeta(traceId=resolved, pagination=pagination),
    ).model_dump(exclude_none=False, mode="json")


def err(
    *,
    code: str,
    message: str,
    http_status: int,
    details: list[ErrorDetail] | None = None,
    trace_id: str | None = None,
) -> dict[str, Any]:
    resolved = _resolve_trace_id(trace_id)
    return Envelope[Any](
        error=ErrorPayload(
            code=code,
            message=message,
            details=details or [],
            traceId=resolved,
        ),
        meta=ResponseMeta(traceId=resolved),
    ).model_dump(exclude_none=False, mode="json")
