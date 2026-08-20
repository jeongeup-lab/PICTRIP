from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def _insert_spot(session: AsyncSession, content_id: str) -> None:
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, show_flag) "
            "VALUES (:cid, 12, :t, 1)"
        ),
        {"cid": content_id, "t": f"title-{content_id}"},
    )


@pytest.mark.asyncio
async def test_same_spot_keeps_a_row_per_day(db_session: AsyncSession) -> None:
    """PK 가 content_id 단독이면 전날 값이 덮여 이력이 사라진다."""
    await _insert_spot(db_session, "cch-1")
    for day, rate in ((date(2026, 8, 18), Decimal("10.0")), (date(2026, 8, 19), Decimal("80.0"))):
        await db_session.execute(
            text(
                "INSERT INTO spot_concentration_daily "
                "(content_id, base_ymd, concentration_rate) VALUES (:cid, :d, :r)"
            ),
            {"cid": "cch-1", "d": day, "r": rate},
        )
    await db_session.commit()

    rows = (
        await db_session.execute(
            text(
                "SELECT base_ymd, concentration_rate FROM spot_concentration_daily "
                "WHERE content_id = 'cch-1' ORDER BY base_ymd"
            )
        )
    ).all()

    assert [(r.base_ymd, float(r.concentration_rate)) for r in rows] == [
        (date(2026, 8, 18), 10.0),
        (date(2026, 8, 19), 80.0),
    ]


@pytest.mark.asyncio
async def test_rerunning_the_same_day_overwrites_that_day_only(db_session: AsyncSession) -> None:
    await _insert_spot(db_session, "cch-2")
    upsert = text(
        "INSERT INTO spot_concentration_daily (content_id, base_ymd, concentration_rate) "
        "VALUES (:cid, :d, :r) ON CONFLICT (content_id, base_ymd) "
        "DO UPDATE SET concentration_rate = EXCLUDED.concentration_rate"
    )
    await db_session.execute(upsert, {"cid": "cch-2", "d": date(2026, 8, 18), "r": Decimal("10.0")})
    await db_session.execute(upsert, {"cid": "cch-2", "d": date(2026, 8, 18), "r": Decimal("55.5")})
    await db_session.commit()

    rows = (
        await db_session.execute(
            text("SELECT concentration_rate FROM spot_concentration_daily WHERE content_id='cch-2'")
        )
    ).all()

    assert len(rows) == 1 and float(rows[0].concentration_rate) == 55.5


@pytest.mark.asyncio
async def test_sync_writes_both_snapshot_and_history(db_session: AsyncSession) -> None:
    """소비처 6곳은 스냅샷을 읽고 추세 분석은 원장을 읽는다 — 한쪽만 쓰면 하나가 죽는다."""
    from scripts.sync_concentration import persist_rows

    await _insert_spot(db_session, "cch-3")

    await persist_rows(
        db_session,
        [
            {
                "content_id": "cch-3",
                "concentration_rate": Decimal("42.5"),
                "base_ymd": date(2026, 8, 20),
                "raw_name": "테스트",
                "signgu_cd": None,
            }
        ],
    )
    await db_session.commit()

    snapshot = (
        await db_session.execute(
            text("SELECT concentration_rate FROM spot_concentration WHERE content_id='cch-3'")
        )
    ).scalar_one()
    history = (
        await db_session.execute(
            text(
                "SELECT base_ymd, concentration_rate FROM spot_concentration_daily "
                "WHERE content_id='cch-3'"
            )
        )
    ).all()

    assert float(snapshot) == 42.5
    assert [(r.base_ymd, float(r.concentration_rate)) for r in history] == [
        (date(2026, 8, 20), 42.5)
    ]


@pytest.mark.asyncio
async def test_sync_keeps_yesterdays_history_row(db_session: AsyncSession) -> None:
    from scripts.sync_concentration import persist_rows

    await _insert_spot(db_session, "cch-4")
    for day, rate in ((date(2026, 8, 19), "10.0"), (date(2026, 8, 20), "80.0")):
        await persist_rows(
            db_session,
            [
                {
                    "content_id": "cch-4",
                    "concentration_rate": Decimal(rate),
                    "base_ymd": day,
                    "raw_name": "테스트",
                    "signgu_cd": None,
                }
            ],
        )
    await db_session.commit()

    days = (
        (
            await db_session.execute(
                text(
                    "SELECT base_ymd FROM spot_concentration_daily "
                    "WHERE content_id='cch-4' ORDER BY base_ymd"
                )
            )
        )
        .scalars()
        .all()
    )

    assert days == [date(2026, 8, 19), date(2026, 8, 20)]
