"""SYS DTOs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class VersionMeta(BaseModel):
    apiVersion: str
    environment: str
    ktoApiStatus: str = "unknown"


# --------------------------------------------------------------------------- #
# Notification preferences (ADR-0013)                                          #
# --------------------------------------------------------------------------- #

# The notification *category* taxonomy is fixed by the `ck_notification_type`
# CHECK constraint on the `notifications` table. We advertise it so the client
# can render category labels; only the master toggle is persisted (see ADR-0013).
NOTIFICATION_CATEGORIES: tuple[str, ...] = (
    "collection",
    "saved_update",
    "course_rec",
    "crowd_change",
)


class NotificationPrefsOut(BaseModel):
    """Current user's notification preferences."""

    enabled: bool
    categories: list[str] = Field(default_factory=lambda: list(NOTIFICATION_CATEGORIES))


class NotificationPrefsUpdate(BaseModel):
    """PUT body — master notification toggle."""

    enabled: bool


# --------------------------------------------------------------------------- #
# Analytics ingest (ADR-0013)                                                  #
# --------------------------------------------------------------------------- #


class AnalyticsEventIn(BaseModel):
    """Client-emitted analytics event. `eventName` <= 64 chars (column limit)."""

    eventName: str = Field(min_length=1, max_length=64)
    properties: dict[str, Any] | None = None


class AnalyticsAck(BaseModel):
    recorded: bool = True
