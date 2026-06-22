"""M2 (0012_spots_image_pool_idx) regression test.

Pins the partial index predicate — autogenerate cannot reproduce it, so a future
migration must not silently drop or widen it.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration


async def test_image_pool_partial_index_exists_with_predicate(db_session: AsyncSession) -> None:
    indexdef = (
        await db_session.execute(
            text("SELECT indexdef FROM pg_indexes WHERE indexname='idx_spots_image_pool'")
        )
    ).scalar_one_or_none()
    assert indexdef is not None
    assert "show_flag = 1" in indexdef
    assert "first_image_url IS NOT NULL" in indexdef
