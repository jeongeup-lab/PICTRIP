"""SYS service layer. Owned by Dev A (notifications, analytics) + Dev B (logs).

Notification preferences (ADR-0013): the persistent master toggle lives on
`user_consents.notification_consent`, owned by USR — SYS reads/writes it through
`users.services` (no cross-module model import). The notification *category*
taxonomy is advertised from the fixed `ck_notification_type` constraint.

Analytics ingest (ADR-0013): a row is appended to `analytics_events` (SYS-owned).
12-month retention is handled out-of-band by a cron on `idx_analytics_old`.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.system.models import AnalyticsEvent
from app.modules.system.schemas import (
    AnalyticsAck,
    AnalyticsEventIn,
    NotificationPrefsOut,
    NotificationPrefsUpdate,
)
from app.modules.users import services as users_services


async def get_notification_prefs(session: AsyncSession, user_id: int) -> NotificationPrefsOut:
    """Return the current user's notification prefs, creating a default
    (all-off) consent row if the user has none yet."""
    enabled = await users_services.get_notification_consent(session, user_id)
    return NotificationPrefsOut(enabled=enabled)


async def update_notification_prefs(
    session: AsyncSession, user_id: int, body: NotificationPrefsUpdate
) -> NotificationPrefsOut:
    """Persist the notification master toggle and return the stored prefs."""
    enabled = await users_services.set_notification_consent(session, user_id, enabled=body.enabled)
    return NotificationPrefsOut(enabled=enabled)


async def record_analytics_event(
    session: AsyncSession, user_id: int, body: AnalyticsEventIn
) -> AnalyticsAck:
    """Append a client analytics event for the current user. Lightweight:
    one INSERT, no enrichment. occurred_at defaults server-side."""
    properties: dict[str, Any] | None = body.properties
    event = AnalyticsEvent(
        user_id=user_id,
        event_name=body.eventName,
        properties=properties,
    )
    session.add(event)
    await session.commit()
    return AnalyticsAck(recorded=True)
