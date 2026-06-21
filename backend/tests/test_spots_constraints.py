"""SPT DB-level constraint regression tests (migration 0003_spt_tables).

Six rules live in the DB schema for SPT; this file pins them so a future
migration can't loosen them silently:

- `spots.cpyrht_div_cd` ∈ {NULL, Type1, Type3} (KTO copyright classification, core to the data policy)
- `spots.show_flag` ∈ {0, 1}
- `spot_moods.confidence` ∈ [0.0, 1.0]
- `spot_moods.source` ∈ {code, image, manual}
- `spot_moods` composite PK is enforced (no duplicate (content_id, mood_id))
- regions seed is present (17 sido) so FKs resolve out of the box
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.spots.models import Spot, SpotMood

pytestmark = pytest.mark.integration


async def _make_spot(session: AsyncSession, content_id: str = "SPT-1") -> Spot:
    spot = Spot(content_id=content_id, content_type_id=12, title=f"t-{content_id}")
    session.add(spot)
    await session.flush()
    return spot


async def test_spots_cpyrht_div_cd_check_rejects_bad_value(
    db_session: AsyncSession,
) -> None:
    db_session.add(
        Spot(
            content_id="SPT-BAD-CPYRHT",
            content_type_id=12,
            title="bad",
            cpyrht_div_cd="Type2",  # ⛔ only Type1 / Type3 / NULL allowed
        )
    )
    with pytest.raises(IntegrityError, match="ck_spot_cpyrht_div_cd"):
        await db_session.flush()


async def test_spots_show_flag_check_rejects_out_of_range(
    db_session: AsyncSession,
) -> None:
    db_session.add(
        Spot(
            content_id="SPT-BAD-FLAG",
            content_type_id=12,
            title="bad",
            show_flag=2,  # ⛔ only 0 or 1
        )
    )
    with pytest.raises(IntegrityError, match="ck_spot_show_flag"):
        await db_session.flush()


async def test_spot_moods_confidence_out_of_range_rejected(
    db_session: AsyncSession,
) -> None:
    await _make_spot(db_session, "SPT-CONF")
    db_session.add(
        SpotMood(
            content_id="SPT-CONF",
            mood_id=1,
            confidence=1.5,  # ⛔ must be ≤ 1.0
            source="code",
        )
    )
    with pytest.raises(IntegrityError, match="ck_spot_mood_confidence"):
        await db_session.flush()


async def test_spot_moods_source_check_rejects_unknown(
    db_session: AsyncSession,
) -> None:
    await _make_spot(db_session, "SPT-SRC")
    db_session.add(
        SpotMood(
            content_id="SPT-SRC",
            mood_id=1,
            confidence=0.5,
            source="auto",  # ⛔ not in {code, image, manual}
        )
    )
    with pytest.raises(IntegrityError, match="ck_spot_mood_source"):
        await db_session.flush()


async def test_spot_moods_composite_pk_rejects_duplicate(
    db_session: AsyncSession,
) -> None:
    await _make_spot(db_session, "SPT-DUP")
    db_session.add(SpotMood(content_id="SPT-DUP", mood_id=1, confidence=0.5, source="code"))
    await db_session.flush()
    db_session.add(SpotMood(content_id="SPT-DUP", mood_id=1, confidence=0.9, source="image"))
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_regions_seed_includes_17_sido(db_session: AsyncSession) -> None:
    count = await db_session.scalar(text("SELECT count(*) FROM regions"))
    assert count == 17

    # Spot-check three: a metropolitan city, a province, a special self-governing province from the post-2024 set
    seoul = await db_session.scalar(
        text("SELECT ldong_regn_nm FROM regions WHERE ldong_regn_cd = '11'")
    )
    gangwon = await db_session.scalar(
        text("SELECT ldong_regn_nm FROM regions WHERE ldong_regn_cd = '51'")
    )
    jeonbuk = await db_session.scalar(
        text("SELECT ldong_regn_nm FROM regions WHERE ldong_regn_cd = '52'")
    )
    assert seoul == "서울특별시"
    assert gangwon == "강원특별자치도"
    assert jeonbuk == "전북특별자치도"
