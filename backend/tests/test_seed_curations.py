"""scripts/seed_curations.py — idempotent 6 region + 3 mood curations."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from scripts import seed_curations


async def _count(session: AsyncSession, type_: str) -> int:
    row = await session.execute(
        text("SELECT count(*) FROM curations WHERE type = :t AND is_published = true"),
        {"t": type_},
    )
    return int(row.scalar_one())


async def test_seed_inserts_six_region_three_mood(db_session: AsyncSession) -> None:
    inserted = await seed_curations.seed(db_session)
    await db_session.flush()

    assert inserted == 9
    assert await _count(db_session, "region") == 6
    assert await _count(db_session, "mood") == 3


async def test_seeded_rows_satisfy_ck_curation_scope(db_session: AsyncSession) -> None:
    await seed_curations.seed(db_session)
    await db_session.flush()

    # region rows must have region_cd; mood rows must have mood_id
    bad_region = await db_session.execute(
        text("SELECT count(*) FROM curations WHERE type='region' AND region_cd IS NULL")
    )
    bad_mood = await db_session.execute(
        text("SELECT count(*) FROM curations WHERE type='mood' AND mood_id IS NULL")
    )
    assert int(bad_region.scalar_one()) == 0
    assert int(bad_mood.scalar_one()) == 0

    # every region_cd resolves to a real region; every mood_id to a real mood
    orphan_region = await db_session.execute(
        text(
            "SELECT count(*) FROM curations c WHERE c.type='region' "
            "AND NOT EXISTS (SELECT 1 FROM regions r WHERE r.ldong_regn_cd = c.region_cd)"
        )
    )
    orphan_mood = await db_session.execute(
        text(
            "SELECT count(*) FROM curations c WHERE c.type='mood' "
            "AND NOT EXISTS (SELECT 1 FROM moods m WHERE m.id = c.mood_id)"
        )
    )
    assert int(orphan_region.scalar_one()) == 0
    assert int(orphan_mood.scalar_one()) == 0


async def test_seed_is_idempotent(db_session: AsyncSession) -> None:
    first = await seed_curations.seed(db_session)
    await db_session.flush()
    second = await seed_curations.seed(db_session)
    await db_session.flush()

    assert first == 9
    assert second == 0
    assert await _count(db_session, "region") == 6
    assert await _count(db_session, "mood") == 3


async def test_titles_preserve_newline_verbatim(db_session: AsyncSession) -> None:
    await seed_curations.seed(db_session)
    await db_session.flush()

    row = await db_session.execute(
        text("SELECT title, subtitle FROM curations WHERE slug = 'region-jeju'")
    )
    title, subtitle = row.one()
    assert title == "제주, 매일 가도\n새로운 섬"
    assert subtitle == "제주에서 가장 사진 잘 받는 곳 →"
