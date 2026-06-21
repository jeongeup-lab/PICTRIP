"""SPT list_spots_by_mood region filter (Gap C)."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ResourceNotFound, ValidationFailed
from app.modules.spots.services import list_spots_by_mood


async def _seed_spot_in_region(
    session: AsyncSession, content_id: str, mood_code: str, region_cd: str
) -> None:
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, first_image_url, "
            "show_flag, ldong_regn_cd) "
            "VALUES (:cid, 12, :t, 'http://kto/i.jpg', 1, :rc)"
        ),
        {"cid": content_id, "t": f"title-{content_id}", "rc": region_cd},
    )
    await session.execute(
        text(
            "INSERT INTO spot_moods (content_id, mood_id, confidence, source) "
            "SELECT :cid, id, 1.0, 'manual' FROM moods WHERE code = :code"
        ),
        {"cid": content_id, "code": mood_code},
    )


@pytest.mark.asyncio
async def test_region_filter_includes_matching_excludes_other(db_session: AsyncSession) -> None:
    await _seed_spot_in_region(db_session, "rf_gangwon", "sea", "51")
    await _seed_spot_in_region(db_session, "rf_jeju", "sea", "50")

    rows = await list_spots_by_mood(db_session, "sea", limit=10000, region="51")
    cids = {r.content_id for r in rows}
    assert "rf_gangwon" in cids
    assert "rf_jeju" not in cids


@pytest.mark.asyncio
async def test_no_region_includes_all_regions(db_session: AsyncSession) -> None:
    await _seed_spot_in_region(db_session, "rf_g2", "sea", "51")
    await _seed_spot_in_region(db_session, "rf_j2", "sea", "50")

    rows = await list_spots_by_mood(db_session, "sea", limit=10000)
    cids = {r.content_id for r in rows}
    assert {"rf_g2", "rf_j2"}.issubset(cids)


@pytest.mark.asyncio
async def test_empty_region_is_no_filter(db_session: AsyncSession) -> None:
    await _seed_spot_in_region(db_session, "rf_g3", "sea", "51")
    await _seed_spot_in_region(db_session, "rf_j3", "sea", "50")

    rows = await list_spots_by_mood(db_session, "sea", limit=10000, region="   ")
    cids = {r.content_id for r in rows}
    assert {"rf_g3", "rf_j3"}.issubset(cids)


@pytest.mark.asyncio
async def test_unknown_region_raises_validation(db_session: AsyncSession) -> None:
    with pytest.raises(ValidationFailed):
        await list_spots_by_mood(db_session, "sea", limit=8, region="99")


@pytest.mark.asyncio
async def test_unknown_mood_checked_before_region(db_session: AsyncSession) -> None:
    with pytest.raises(ResourceNotFound):
        await list_spots_by_mood(db_session, "doesnotexist", limit=8, region="51")
