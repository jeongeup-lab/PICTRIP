"""SPT pick_active_spot_by_seed — deterministic daily-inspo spot picker."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.spots.services import pick_active_spot_by_seed


async def _seed_spot(
    session: AsyncSession,
    content_id: str,
    *,
    image_url: str | None = "http://kto.example/i.jpg",
    show_flag: int = 1,
) -> None:
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, first_image_url, show_flag) "
            "VALUES (:cid, 12, :t, :img, :sf)"
        ),
        {"cid": content_id, "t": f"title-{content_id}", "img": image_url, "sf": show_flag},
    )


@pytest.mark.asyncio
async def test_returns_none_on_empty_pool(db_session: AsyncSession) -> None:
    # Clear the pool within this transaction (rolled back after the test).
    await db_session.execute(
        text(
            "UPDATE spots SET show_flag = 0 "
            "WHERE show_flag = 1 AND first_image_url IS NOT NULL AND first_image_url <> ''"
        )
    )
    assert await pick_active_spot_by_seed(db_session, 12345) is None


@pytest.mark.asyncio
async def test_same_seed_returns_same_spot(db_session: AsyncSession) -> None:
    for cid in ("pas_a", "pas_b", "pas_c"):
        await _seed_spot(db_session, cid)

    first = await pick_active_spot_by_seed(db_session, 999)
    second = await pick_active_spot_by_seed(db_session, 999)
    assert first is not None
    assert second is not None
    assert first.content_id == second.content_id


@pytest.mark.asyncio
async def test_seed_modulo_wraps_past_count(db_session: AsyncSession) -> None:
    await _seed_spot(db_session, "pas_only")
    # seed far larger than the pool size must still resolve via modulo.
    row = await pick_active_spot_by_seed(db_session, 10**18)
    assert row is not None


@pytest.mark.asyncio
async def test_excludes_inactive_imageless_and_empty_image(db_session: AsyncSession) -> None:
    await _seed_spot(db_session, "pas_hidden", show_flag=0)
    await _seed_spot(db_session, "pas_noimg", image_url=None)
    await _seed_spot(db_session, "pas_emptyimg", image_url="")
    await _seed_spot(db_session, "pas_good")

    # The ineligible content_ids must never appear across many seeds.
    results = [await pick_active_spot_by_seed(db_session, s) for s in range(20)]
    returned_ids = {r.content_id for r in results if r is not None}
    assert "pas_hidden" not in returned_ids
    assert "pas_noimg" not in returned_ids
    assert "pas_emptyimg" not in returned_ids
