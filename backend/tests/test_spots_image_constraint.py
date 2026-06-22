"""spot_images (content_id, sort_order) uniqueness regression (migration 0006)."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_spot_images_unique_content_sort(db_session: AsyncSession) -> None:
    await db_session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, show_flag) "
            "VALUES ('IMG-UQ', 12, 't', 1)"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO spot_images (content_id, origin_image_url, sort_order) "
            "VALUES ('IMG-UQ', 'http://a', 0)"
        )
    )
    with pytest.raises(IntegrityError, match="uq_spot_images_content_sort"):
        await db_session.execute(
            text(
                "INSERT INTO spot_images (content_id, origin_image_url, sort_order) "
                "VALUES ('IMG-UQ', 'http://b', 0)"
            )
        )
        await db_session.flush()
