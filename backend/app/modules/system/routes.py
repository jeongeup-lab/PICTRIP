"""SYS routes. Endpoints mirror API spec §12."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, status

from app.config import settings
from app.core.auth import CurrentUserId
from app.core.db import DbSession
from app.core.schemas import ok
from app.modules.system import services
from app.modules.system.schemas import AnalyticsEventIn, NotificationPrefsUpdate

router = APIRouter(tags=["SYS · system/meta"])


@router.get("/meta/version", status_code=status.HTTP_200_OK, summary="API version/meta")
async def version() -> dict[str, Any]:
    return ok(
        {
            "apiVersion": "1.0.0-dev",
            "environment": settings.ENVIRONMENT,
            "ktoApiStatus": "unknown",
        }
    )


@router.get(
    "/me/notifications",
    status_code=status.HTTP_200_OK,
    summary="My notification settings (creates defaults if absent)",
)
async def get_notifications(user_id: CurrentUserId, session: DbSession) -> dict[str, Any]:
    prefs = await services.get_notification_prefs(session, user_id)
    return ok(prefs.model_dump())


@router.put(
    "/me/notifications",
    status_code=status.HTTP_200_OK,
    summary="Update my notification settings",
)
async def update_notifications(
    body: NotificationPrefsUpdate, user_id: CurrentUserId, session: DbSession
) -> dict[str, Any]:
    prefs = await services.update_notification_prefs(session, user_id, body)
    return ok(prefs.model_dump())


@router.post(
    "/analytics/events",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Record a client analytics event",
)
async def post_analytics_event(
    body: AnalyticsEventIn, user_id: CurrentUserId, session: DbSession
) -> dict[str, Any]:
    ack = await services.record_analytics_event(session, user_id, body)
    return ok(ack.model_dump())
