"""DB-level constraint regression tests for migration 0004_remaining_domains.

Covers the load-bearing CHECK rules on the tables that survive: CRS `courses`
enum checks and SYS `notifications` type check. The dead-table constraint tests
(taste_feedback_events, recommendation_logs, reason_cache, collections, the
DataLab visitor tables) were removed with those tables in migration 0010.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration


async def test_courses_enum_checks_reject_unknown_values(
    db_session: AsyncSession,
) -> None:
    user_id = await db_session.scalar(text("INSERT INTO users (email) VALUES (NULL) RETURNING id"))
    bad_cases = [
        ("week", "normal", "solo", "efficient", "ck_course_duration_type"),
        ("day", "intense", "solo", "efficient", "ck_course_pace_type"),
        ("day", "normal", "pet", "efficient", "ck_course_companion_type"),
        ("day", "normal", "solo", "scenic", "ck_course_course_type"),
    ]
    for dur, pace, comp, ctype, expected_cc in bad_cases:
        with pytest.raises(IntegrityError, match=expected_cc):
            await db_session.execute(
                text(
                    "INSERT INTO courses "
                    "(user_id, name, duration_type, pace_type, companion_type, course_type) "
                    "VALUES (:u, 't', :d, :p, :c, :ct)"
                ),
                {"u": user_id, "d": dur, "p": pace, "c": comp, "ct": ctype},
            )
            await db_session.flush()
        await db_session.rollback()
        # re-create user since rollback dropped it
        user_id = await db_session.scalar(
            text("INSERT INTO users (email) VALUES (NULL) RETURNING id")
        )


async def test_notifications_type_check(db_session: AsyncSession) -> None:
    user_id = await db_session.scalar(text("INSERT INTO users (email) VALUES (NULL) RETURNING id"))
    with pytest.raises(IntegrityError, match="ck_notification_type"):
        await db_session.execute(
            text(
                "INSERT INTO notifications (user_id, type, payload) "
                "VALUES (:u, 'unknown_kind', '{}'::jsonb)"
            ),
            {"u": user_id},
        )
        await db_session.flush()
