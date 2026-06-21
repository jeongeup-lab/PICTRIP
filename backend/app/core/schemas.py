"""JSend envelope — every API response goes through ok()/err().

Mobile mirrors this in mobile/src/lib/api-types.ts — keep in sync.
"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ResponseMeta(BaseModel):
    traceId: str  # auto-injected by TraceIdMiddleware


class ErrorPayload(BaseModel):
    code: str
    message: str


class Envelope(BaseModel, Generic[T]):
    data: T | None = None
    error: ErrorPayload | None = None
    meta: ResponseMeta


def ok(data: T, *, trace_id: str) -> Envelope[T]:
    return Envelope(data=data, error=None, meta=ResponseMeta(traceId=trace_id))


def err(code: str, message: str, *, trace_id: str) -> Envelope[None]:
    return Envelope(data=None, error=ErrorPayload(code=code, message=message), meta=ResponseMeta(traceId=trace_id))
