"""M3 (0013_drop_dead_columns) DB-level regression test.

Pins that the dead columns refresh_token_enc / notification_consent are gone at
head, so the DB matches the post-Task-6/13 ORM. If a future migration re-adds
them, this fails.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration


async def test_dead_columns_absent_at_head(db_session: AsyncSession) -> None:
    rows = (
        await db_session.execute(
            text(
                "SELECT table_name, column_name FROM information_schema.columns "
                "WHERE (table_name='user_auth_providers' "
                "       AND column_name='refresh_token_enc') "
                "   OR (table_name='user_consents' "
                "       AND column_name='notification_consent')"
            )
        )
    ).all()
    assert rows == []
