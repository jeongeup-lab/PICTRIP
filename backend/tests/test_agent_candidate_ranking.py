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


@pytest.fixture(autouse=True)
def _fresh_rank_stats() -> None:
    repositories.reset_rank_stats()


async def _buzz(
    session: AsyncSession,
    cid: str,
    *,
    scope: str,
    blogs: int = 0,
    total: int | None = None,
    recent: float = 0.0,
) -> None:
    await session.execute(
        text(
            "INSERT INTO spot_buzz (content_id, scope, mentions, distinct_blogs, "
            "recent_ratio, blog_total) VALUES (:c, :s, :m, :d, :r, :t)"
        ),
        {"c": cid, "s": scope, "m": blogs, "d": blogs, "r": recent, "t": total},
    )


async def _visual(session: AsyncSession, cid: str, *, kind: str, score: float) -> None:
    await session.execute(
        text(
            "INSERT INTO spot_visual (content_id, photo_type, aesthetic_score) VALUES (:c, :k, :s)"
        ),
        {"c": cid, "k": kind, "s": score},
    )


async def test_a_famous_spot_outranks_an_unknown_one_that_the_crowd_feed_tracks(
    seeded: AsyncSession,
) -> None:
    await _buzz(seeded, "9000001", scope="base", total=500_000)
    await _buzz(seeded, "9000002", scope="base", total=900)
    await _buzz(seeded, "9000004", scope="base", total=1_200)
    repositories.reset_rank_stats()

    ids = await _ids(seeded, seed="2026-08-11")

    assert ids[0] == "9000001"


async def test_an_unscanned_spot_is_treated_as_typical_rather_than_as_never_mentioned(
    seeded: AsyncSession,
) -> None:
    await _buzz(seeded, "9000002", scope="base", total=900)
    await _buzz(seeded, "9000004", scope="base", total=1_200)
    await _buzz(seeded, "9000006", scope="base", total=40)
    repositories.reset_rank_stats()

    ids = await _ids(seeded, seed="2026-08-11")

    assert ids.index("9000001") < ids.index("9000006")


async def test_buzz_for_the_asked_theme_counts_and_buzz_for_another_theme_does_not(
    seeded: AsyncSession,
) -> None:
    await _buzz(seeded, "9000001", scope="부산:spot", blogs=5)
    await _buzz(seeded, "9000002", scope="부산:cafe", blogs=5)

    ids = await _ids(seeded, seed="2026-08-11")

    assert ids.index("9000001") < ids.index("9000002")


async def test_photo_quality_is_judged_inside_its_own_type_not_across_types(
    seeded: AsyncSession,
) -> None:
    await _visual(seeded, "9000001", kind="view", score=0.05)
    await _visual(seeded, "9000002", kind="view", score=0.19)
    await _visual(seeded, "9000004", kind="food", score=0.08)
    await _visual(seeded, "9000006", kind="food", score=-0.13)
    repositories.reset_rank_stats()

    ids = await _ids(seeded, seed="2026-08-11")

    assert ids.index("9000002") < ids.index("9000001")
    assert ids.index("9000004") < ids.index("9000006")
