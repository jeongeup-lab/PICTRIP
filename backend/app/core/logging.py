"""Structured logging via structlog (JSON off-local); each line carries the request traceId."""

from __future__ import annotations

import logging
import sys
from contextvars import ContextVar

import structlog

from app.config import settings

_trace_id_ctx: ContextVar[str | None] = ContextVar("trace_id", default=None)


def set_trace_id(trace_id: str) -> None:
    _trace_id_ctx.set(trace_id)


def get_trace_id() -> str | None:
    return _trace_id_ctx.get()


def _inject_trace_id(_logger, _name, event_dict):  # type: ignore[no-untyped-def]
    trace_id = _trace_id_ctx.get()
    if trace_id:
        event_dict["traceId"] = trace_id
    return event_dict


def configure_logging() -> None:
    """Configure structlog + stdlib logging. Called once at app startup."""
    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        timestamper,
        _inject_trace_id,
    ]

    renderer: structlog.types.Processor = (
        structlog.dev.ConsoleRenderer()
        if settings.ENVIRONMENT == "local"
        else structlog.processors.JSONRenderer()
    )

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelNamesMapping().get(settings.LOG_LEVEL.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=settings.LOG_LEVEL.upper(),
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    logger: structlog.stdlib.BoundLogger = structlog.get_logger(name)
    return logger
