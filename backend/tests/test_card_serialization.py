"""Canonical SpotCard serialization: subtype-category join."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.spots.schemas import SpotCard
from app.modules.spots.services.cards import (
    load_active_spot_cards_by_ids,
    load_spot_cards_by_ids,
)


def test_spotcard_category_defaults_none_and_omittable() -> None:
    card = SpotCard(contentId="c1", title="t", firstImageUrl=None)
    assert card.category is None

    enriched = SpotCard(contentId="c2", title="t", category="찻집")
    assert enriched.category == "찻집"


async def _seed_spot(
    session: AsyncSession,
    cid: str,
    *,
    l3: str | None = None,
    l3_nm: str | None = None,
    show: int = 1,
) -> None:
    if l3 is not None:
        await session.execute(
            text(
                "INSERT INTO lcls_systm_codes (lcls_systm3_cd, lcls_systm3_nm) "
                "VALUES (:l3, :nm) ON CONFLICT DO NOTHING"
            ),
            {"l3": l3, "nm": l3_nm or l3},
        )
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, first_image_url, "
            "show_flag, lcls_systm3) VALUES (:cid, 12, :t, 'http://kto/i.jpg', :show, :l3)"
        ),
        {"cid": cid, "t": f"t-{cid}", "show": show, "l3": l3},
    )


async def test_load_spot_cards_carry_subtype_category(db_session: AsyncSession) -> None:
    await _seed_spot(db_session, "s1", l3="A01010100", l3_nm="사적지")
    await _seed_spot(db_session, "s2")  # no lcls_systm3 → LEFT JOIN yields None

    rows = await load_spot_cards_by_ids(db_session, ["s1", "s2"])
    assert rows["s1"].lcls_systm3_nm == "사적지"
    assert rows["s2"].lcls_systm3_nm is None


async def test_load_active_spot_cards_carry_subtype_category(db_session: AsyncSession) -> None:
    await _seed_spot(db_session, "a1", l3="C01010100", l3_nm="찻집")
    await _seed_spot(db_session, "hidden", l3="C01010100", l3_nm="찻집", show=0)

    rows = await load_active_spot_cards_by_ids(db_session, ["a1", "hidden"])
    assert rows["a1"].lcls_systm3_nm == "찻집"
    assert "hidden" not in rows  # show_flag=0 excluded
