"""DB-level regression tests for migration 0005_schema_v1_2_alignment.

Pins the structural changes that v1.2 introduced so a future migration can't
quietly undo them:

- spots.overview is gone, spot_details.overview is the only overview column
- related_spots / tats_name_mappings tables are gone (Redis-only, ADR-0005)

The `mood_prototypes` constraint tests were removed with that table in
migration 0010.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration


async def test_spots_overview_column_removed(db_session: AsyncSession) -> None:
    exists = await db_session.scalar(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = 'spots' AND column_name = 'overview'"
        )
    )
    assert exists is None


async def test_spot_details_overview_column_present(db_session: AsyncSession) -> None:
    exists = await db_session.scalar(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = 'spot_details' AND column_name = 'overview'"
        )
    )
    assert exists == 1


@pytest.mark.parametrize("dropped_table", ["related_spots", "tats_name_mappings"])
async def test_tarrlte_tables_dropped(db_session: AsyncSession, dropped_table: str) -> None:
    exists = await db_session.scalar(
        text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = :t"
        ),
        {"t": dropped_table},
    )
    assert exists is None, f"{dropped_table} should be dropped per ADR-0005"
