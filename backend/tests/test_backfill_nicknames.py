"""scripts/backfill_nicknames.py — random nicknames for pre-generator accounts."""

from __future__ import annotations

import random
import re

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from scripts import backfill_nicknames

_NICKNAME_RE = re.compile(r"^[가-힣]+\d{2,3}$")


async def _insert_user(
    session: AsyncSession,
    email: str,
    name: str | None,
    deleted: bool = False,
) -> int:
    row = await session.execute(
        text(
            "INSERT INTO users (email, name, deleted_at) "
            "VALUES (:e, :n, CASE WHEN :d THEN now() END) RETURNING id"
        ),
        {"e": email, "n": name, "d": deleted},
    )
    return int(row.scalar_one())


async def _name_of(session: AsyncSession, user_id: int) -> str | None:
    row = await session.execute(text("SELECT name FROM users WHERE id = :i"), {"i": user_id})
    return row.scalar_one()


async def test_backfills_only_active_nameless_users(db_session: AsyncSession) -> None:
    nameless = await _insert_user(db_session, "a@test.dev", None)
    named = await _insert_user(db_session, "b@test.dev", "직접지은이름")
    deleted = await _insert_user(db_session, "c@test.dev", None, deleted=True)

    updated = await backfill_nicknames.backfill(db_session)
    await db_session.flush()

    assert updated == 1
    filled = await _name_of(db_session, nameless)
    assert filled is not None and _NICKNAME_RE.fullmatch(filled)
    assert len(filled) <= 50
    assert await _name_of(db_session, named) == "직접지은이름"
    assert await _name_of(db_session, deleted) is None


async def test_backfill_is_idempotent(db_session: AsyncSession) -> None:
    user_id = await _insert_user(db_session, "d@test.dev", None)

    first = await backfill_nicknames.backfill(db_session)
    await db_session.flush()
    kept = await _name_of(db_session, user_id)
    second = await backfill_nicknames.backfill(db_session)
    await db_session.flush()

    assert first == 1
    assert second == 0
    assert await _name_of(db_session, user_id) == kept


async def test_backfill_deterministic_with_seeded_rng(db_session: AsyncSession) -> None:
    await _insert_user(db_session, "e@test.dev", None)
    await _insert_user(db_session, "f@test.dev", None)

    updated = await backfill_nicknames.backfill(db_session, rng=random.Random(42))
    await db_session.flush()

    expected_rng = random.Random(42)
    from app.modules.users.nickname import generate_nickname

    expected = [generate_nickname(expected_rng), generate_nickname(expected_rng)]
    rows = await db_session.execute(
        text("SELECT name FROM users WHERE email IN ('e@test.dev','f@test.dev') ORDER BY id")
    )
    assert [r[0] for r in rows] == expected
    assert updated == 2
