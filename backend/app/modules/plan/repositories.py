from __future__ import annotations

from typing import Any

from app.core.db import AsyncSession
from app.modules.plan.models import Plan


async def create_plan(
    session: AsyncSession,
    *,
    source_kind: str,
    source_url: str | None,
    source_title: str | None,
    payload: dict[str, Any],
) -> Plan:
    plan = Plan(
        source_kind=source_kind,
        source_url=source_url,
        source_title=source_title,
        payload=payload,
    )
    session.add(plan)
    await session.flush()
    return plan


async def get_plan(session: AsyncSession, plan_id: int) -> Plan | None:
    return await session.get(Plan, plan_id)
