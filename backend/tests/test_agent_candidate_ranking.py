from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agent import repositories

REGION = "부산광역시 해운대구"


async def _seed(session: AsyncSession, cid: str, *, rate: float | None) -> None:
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, addr1, first_image_url, "
            "show_flag, lcls_systm1) "
            "VALUES (:cid, 12, :t, :addr, 'http://kto/i.jpg', 1, 'NA')"
        ),
        {"cid": cid, "t": f"t-{cid}", "addr": f"{REGION} {cid}로"},
    )
    if rate is not None:
        await session.execute(
            text(
                "INSERT INTO spot_concentration "
                "(content_id, concentration_rate, base_ymd, raw_name) "
                "VALUES (:cid, :rate, DATE '2026-07-01', :rn)"
            ),
            {"cid": cid, "rate": rate, "rn": f"n-{cid}"},
        )


async def _ids(session: AsyncSession, *, seed: str) -> list[str]:
    rows = await repositories.find_candidates(
        session,
        codes=None,
        region_prefixes=[REGION],
        limit=50,
        order="id",
        rank_seed=seed,
    )
    return [row.content_id for row in rows]


@pytest.fixture
async def seeded(db_session: AsyncSession) -> AsyncSession:
    await _seed(db_session, "9000001", rate=None)
    await _seed(db_session, "9000002", rate=None)
    await _seed(db_session, "9000003", rate=41.0)
    await _seed(db_session, "9000004", rate=None)
    await _seed(db_session, "9000005", rate=62.0)
    await _seed(db_session, "9000006", rate=None)
    return db_session


async def test_spots_the_crowd_feed_tracks_come_before_the_ones_it_does_not(
    seeded: AsyncSession,
) -> None:
    ids = await _ids(seeded, seed="2026-08-11")

    assert set(ids[:2]) == {"9000003", "9000005"}


async def test_the_same_day_gives_the_same_list(seeded: AsyncSession) -> None:
    assert await _ids(seeded, seed="2026-08-11") == await _ids(seeded, seed="2026-08-11")


async def test_a_different_day_reshuffles_the_untracked_tail(seeded: AsyncSession) -> None:
    monday = await _ids(seeded, seed="2026-08-11")
    friday = await _ids(seeded, seed="2026-08-15")

    assert set(monday) == set(friday)
    assert monday != friday


async def test_every_seeded_spot_still_comes_back(seeded: AsyncSession) -> None:
    ids = await _ids(seeded, seed="2026-08-11")

    assert sorted(ids) == [f"900000{n}" for n in range(1, 7)]


def test_the_default_seed_is_todays_date_in_seoul() -> None:
    seed = repositories.rank_seed_for_today()

    assert len(seed) == 10
    assert seed.count("-") == 2
