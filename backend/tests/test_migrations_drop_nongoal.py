"""M4 (0014_drop_nongoal_tables) DB-level regression test.

Pins that the non-goal tables (courses / course_days / course_items /
notifications / analytics_events) are dropped at head, while spot_concentration
(the congestion source) is preserved.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

_DROPPED = (
    "courses",
    "course_days",
    "course_items",
    "notifications",
    "analytics_events",
)


async def test_nongoal_tables_absent_concentration_present(db_session: AsyncSession) -> None:
    present = {
        name
        for (name,) in (
            await db_session.execute(
                text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
            )
        ).all()
    }
    assert not (set(_DROPPED) & present), (
        f"non-goal tables still present: {set(_DROPPED) & present}"
    )
    assert "spot_concentration" in present
