"""Canonical SpotCard serialization: bucket_congestion, load_congestion, subtype-category join."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.spots.schemas import SpotCard
from app.modules.spots.services.cards import (
    bucket_congestion,
    load_active_spot_cards_by_ids,
    load_congestion,
    load_spot_cards_by_ids,
)


def test_congestion_buckets() -> None:
    assert bucket_congestion(10) == "low"
    assert bucket_congestion(50) == "medium"
    assert bucket_congestion(90) == "high"
    assert bucket_congestion(None) is None
    # Exact boundaries: <34 low, 34..66 medium (inclusive), >66 high.
    assert bucket_congestion(34) == "medium"
    assert bucket_congestion(66) == "medium"
    assert bucket_congestion(33.9) == "low"
    assert bucket_congestion(66.1) == "high"


def test_spotcard_congestion_defaults_none_and_omittable() -> None:
    card = SpotCard(contentId="c1", title="t", firstImageUrl=None)
    assert card.category is None
    assert card.congestion is None

    enriched = SpotCard(contentId="c2", title="t", category="찻집", congestion="medium")
    assert enriched.category == "찻집"
    assert enriched.congestion == "medium"


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


async def _seed_concentration(session: AsyncSession, cid: str, rate: float) -> None:
    await session.execute(
        text(
            "INSERT INTO spot_concentration (content_id, concentration_rate, base_ymd, raw_name) "
            "VALUES (:cid, :rate, CURRENT_DATE, :nm)"
        ),
        {"cid": cid, "rate": rate, "nm": f"raw-{cid}"},
    )


async def test_load_congestion_buckets_and_misses(db_session: AsyncSession) -> None:
    await _seed_spot(db_session, "lo")
    await _seed_spot(db_session, "mid")
    await _seed_spot(db_session, "hi")
    await _seed_spot(db_session, "none")  # no concentration row
    await _seed_concentration(db_session, "lo", 10)
    await _seed_concentration(db_session, "mid", 50)
    await _seed_concentration(db_session, "hi", 90)

    out = await load_congestion(db_session, ["lo", "mid", "hi", "none"])
    assert out == {"lo": "low", "mid": "medium", "hi": "high"}
    # A content_id with no spot_concentration row is simply absent (caller defaults None).
    assert "none" not in out


async def test_load_congestion_empty_input() -> None:
    # No-op fast path — no session call.
    assert await load_congestion(None, []) == {}  # type: ignore[arg-type]


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
