"""M1 (0011_curations) DB-level regression tests.

Pins the curations / curation_spots tables and their named CHECK constraints so a
future migration can't loosen them silently.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration


async def test_curations_tables_exist(db_session: AsyncSession) -> None:
    rows = (
        (
            await db_session.execute(
                text(
                    "SELECT tablename FROM pg_tables "
                    "WHERE tablename IN ('curations','curation_spots')"
                )
            )
        )
        .scalars()
        .all()
    )
    assert {"curations", "curation_spots"} <= set(rows)


async def test_named_check_constraints_present(db_session: AsyncSession) -> None:
    rows = (
        (
            await db_session.execute(
                text(
                    "SELECT conname FROM pg_constraint "
                    "WHERE conrelid='curations'::regclass AND contype='c'"
                )
            )
        )
        .scalars()
        .all()
    )
    assert {"ck_curation_type", "ck_curation_scope"} <= set(rows)


async def test_scope_check_rejects_region_without_region_cd(db_session: AsyncSession) -> None:
    with pytest.raises(IntegrityError, match="ck_curation_scope"):
        await db_session.execute(
            text("INSERT INTO curations (type, slug, title) VALUES ('region','bad','x')")
        )
        await db_session.flush()


async def test_type_check_rejects_unknown_type(db_session: AsyncSession) -> None:
    # An unknown type fails both ck_curation_type and ck_curation_scope (no scope
    # branch matches); Postgres may report either — assert the check layer rejects.
    with pytest.raises(IntegrityError, match=r"ck_curation_(type|scope)"):
        await db_session.execute(
            text("INSERT INTO curations (type, slug, title) VALUES ('weird','bad2','x')")
        )
        await db_session.flush()
