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


@pytest.mark.parametrize("index_name", ["idx_spots_title_trgm", "idx_spots_addr1_trgm"])
async def test_trgm_indexes_are_declared_in_orm(db_session: AsyncSession, index_name: str) -> None:
    """ORM 에 없으면 autogenerate 가 매번 DROP 을 제안한다 — 놓치면 검색이 죽는다."""
    from app.modules.spots.models import Spot

    assert index_name in {index.name for index in Spot.__table__.indexes}
    assert (
        await db_session.scalar(
            text("SELECT 1 FROM pg_indexes WHERE indexname = :name"), {"name": index_name}
        )
        == 1
    )
