from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.plan.models import Plan


async def insert_plan(
    session: AsyncSession,
    *,
    plan_id: uuid.UUID,
    thread_id: str,
    user_id: int | None,
    payload: dict[str, Any],
) -> Plan:
    plan = Plan(id=plan_id, thread_id=thread_id, user_id=user_id, payload=payload)
    session.add(plan)
    await session.commit()
    return plan


async def get_plan(session: AsyncSession, plan_id: uuid.UUID) -> Plan | None:
    result: Plan | None = await session.scalar(select(Plan).where(Plan.id == plan_id))
    return result
