"""집중률 Hot/Hidden 서빙 쿼리 — load_hot_spots / load_hidden_spots."""

from __future__ import annotations

from dataclasses import dataclass

import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.spots.services import load_hidden_spots, load_hot_spots


@dataclass(frozen=True)
class SeededConcentration:
    highest_id: str
    lowest_quality_ok_id: str
    no_overview_id: str


async def _seed_region(session: AsyncSession) -> None:
    await session.execute(
        text(
            "INSERT INTO regions (ldong_regn_cd, ldong_regn_nm) VALUES (:c, :n) "
            "ON CONFLICT DO NOTHING"
        ),
        {"c": "26", "n": "부산"},
    )
    await session.execute(
        text(
            "INSERT INTO sigungus (ldong_signgu_cd, ldong_regn_cd, ldong_signgu_nm) "
            "VALUES (:c, :r, :n) ON CONFLICT DO NOTHING"
        ),
        {"c": "26380", "r": "26", "n": "사하구"},
    )


async def _seed_spot(
    session: AsyncSession,
    cid: str,
    *,
    rate: str,
    show: int = 1,
    img: str | None = "http://kto/i.jpg",
    overview: str | None = None,
) -> None:
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, first_image_url, "
            "show_flag, ldong_regn_cd, ldong_signgu_cd) "
            "VALUES (:cid, 12, :t, :img, :show, '26', '26380')"
        ),
        {"cid": cid, "t": f"t-{cid}", "img": img, "show": show},
    )
    await session.execute(
        text(
            "INSERT INTO spot_concentration "
            "(content_id, concentration_rate, base_ymd, raw_name) "
            "VALUES (:cid, :rate, DATE '2026-07-01', :rn)"
        ),
        {"cid": cid, "rate": rate, "rn": f"n-{cid}"},
    )
    if overview is not None:
        await session.execute(
            text(
                "INSERT INTO spot_details (content_id, content_type_id, overview) "
                "VALUES (:cid, 12, :ov)"
            ),
            {"cid": cid, "ov": overview},
        )


@pytest_asyncio.fixture
async def seeded_concentration(db_session: AsyncSession) -> SeededConcentration:
    await _seed_region(db_session)
    await _seed_spot(db_session, "c90", rate="90.00", overview="설명 90")
    await _seed_spot(db_session, "c60", rate="60.00", overview="설명 60")
    await _seed_spot(db_session, "c30", rate="30.00", overview=None)
    await _seed_spot(db_session, "c10", rate="10.00", overview="설명 10")
    await _seed_spot(db_session, "c95hidden", rate="95.00", show=0, overview="설명 95")
    await db_session.flush()
    return SeededConcentration(
        highest_id="c90",
        lowest_quality_ok_id="c10",
        no_overview_id="c30",
    )


async def test_hot_orders_by_rate_desc_with_rank(
    db_session: AsyncSession, seeded_concentration: SeededConcentration
) -> None:
    rows = await load_hot_spots(db_session, limit=10)
    assert [r.rank for r in rows] == list(range(1, len(rows) + 1))
    assert rows[0].content_id == seeded_concentration.highest_id
    assert all(r.first_image_url for r in rows)
    assert seeded_concentration.no_overview_id in [r.content_id for r in rows]
    assert "c95hidden" not in [r.content_id for r in rows]
    assert rows[0].region_label == "부산광역시 사하구"


async def test_hidden_orders_by_rate_asc_and_requires_quality(
    db_session: AsyncSession, seeded_concentration: SeededConcentration
) -> None:
    rows = await load_hidden_spots(db_session, limit=10)
    assert rows[0].content_id == seeded_concentration.lowest_quality_ok_id
    assert seeded_concentration.no_overview_id not in [r.content_id for r in rows]
    assert "c95hidden" not in [r.content_id for r in rows]
    assert [r.rank for r in rows] == list(range(1, len(rows) + 1))


async def test_hot_respects_limit(
    db_session: AsyncSession, seeded_concentration: SeededConcentration
) -> None:
    rows = await load_hot_spots(db_session, limit=2)
    assert [r.content_id for r in rows] == ["c90", "c60"]
