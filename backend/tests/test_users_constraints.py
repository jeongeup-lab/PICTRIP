from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import User

pytestmark = pytest.mark.integration


async def test_email_unique_blocks_duplicate_among_active(
    db_session: AsyncSession,
) -> None:
    db_session.add_all(
        [
            User(email="dup-active@example.com"),
            User(email="dup-active@example.com"),
        ]
    )
    with pytest.raises(IntegrityError, match="idx_users_email_active"):
        await db_session.flush()


async def test_email_partial_unique_allows_reuse_after_soft_delete(
    db_session: AsyncSession,
) -> None:
    u1 = User(email="reuse@example.com")
    db_session.add(u1)
    await db_session.flush()

    await db_session.execute(
        text("UPDATE users SET deleted_at = NOW() WHERE id = :uid"),
        {"uid": u1.id},
    )

    db_session.add(User(email="reuse@example.com"))
    await db_session.flush()

    count = await db_session.scalar(
        text("SELECT count(*) FROM users WHERE email = :e"),
        {"e": "reuse@example.com"},
    )
    assert count == 2
