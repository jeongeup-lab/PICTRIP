from __future__ import annotations

import pytest_asyncio
from fakeredis.aioredis import FakeRedis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.feed.services.concentration_channels import (
    _cache_key,
    load_concentration_channel_cached,
)


async def _seed(
    session: AsyncSession, cid: str, *, rate: str, overview: str | None, cpyrht: str | None = None
) -> None:
    await session.execute(
        text(
            "INSERT INTO regions (ldong_regn_cd, ldong_regn_nm) VALUES ('26', '부산광역시') "
            "ON CONFLICT DO NOTHING"
        )
    )
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, first_image_url, "
            "show_flag, ldong_regn_cd, lcls_systm1, cpyrht_div_cd) "
            "VALUES (:cid, 12, :t, 'http://kto/i.jpg', 1, '26', 'NA', :cp)"
        ),
        {"cid": cid, "t": f"t-{cid}", "cp": cpyrht},
    )
    await session.execute(
        text(
            "INSERT INTO spot_concentration (content_id, concentration_rate, base_ymd, raw_name) "
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
async def seeded(db_session: AsyncSession) -> None:
    await _seed(db_session, "h90", rate="90.00", overview="설명 90", cpyrht="Type1")
    await _seed(db_session, "h10", rate="10.00", overview="설명 10")
    await db_session.flush()


async def test_miss_queries_db_and_populates_cache(db_session, seeded) -> None:
    redis = FakeRedis(decode_responses=True)

    cards = await load_concentration_channel_cached(db_session, redis, "hot")

    assert cards[0].content_id == "h90"
    assert cards[0].rank == 1
    assert cards[0].cpyrht_div_cd == "Type1"
    assert cards[1].cpyrht_div_cd is None
    assert await redis.get(_cache_key("hot")) is not None


async def test_hit_serves_from_cache_without_db(db_session, seeded) -> None:
    redis = FakeRedis(decode_responses=True)
    await load_concentration_channel_cached(db_session, redis, "hot")

    await db_session.execute(text("DELETE FROM spot_concentration"))
    await db_session.flush()

    cards = await load_concentration_channel_cached(db_session, redis, "hot")
    assert [c.content_id for c in cards] == ["h90", "h10"]


async def test_hidden_cards_carry_a_quiet_rank_and_no_tag(db_session, seeded) -> None:
    redis = FakeRedis(decode_responses=True)

    cards = await load_concentration_channel_cached(db_session, redis, "hidden")

    assert [c.content_id for c in cards] == ["h10", "h90"]
    assert [c.rank for c in cards] == [1, 2]
    assert all(c.tag is None for c in cards)


async def test_hot_cards_carry_a_crowding_rank_and_no_tag(db_session, seeded) -> None:
    redis = FakeRedis(decode_responses=True)

    cards = await load_concentration_channel_cached(db_session, redis, "hot")

    assert [c.content_id for c in cards] == ["h90", "h10"]
    assert [c.rank for c in cards] == [1, 2]
    assert all(c.tag is None for c in cards)


async def test_empty_result_is_not_cached(db_session) -> None:
    redis = FakeRedis(decode_responses=True)

    cards = await load_concentration_channel_cached(db_session, redis, "hidden")

    assert cards == []
    assert await redis.get(_cache_key("hidden")) is None
