"""REC get_today_inspo — daily-stable inspo spot with Redis caching."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from fakeredis.aioredis import FakeRedis
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ResourceNotFound
from app.modules.recommendations import services as recommendations_services
from app.modules.recommendations.services import (
    _seconds_until_kst_midnight,
    _seed_for_date,
    get_today_inspo,
)


async def _seed_spot(session: AsyncSession, content_id: str) -> None:
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, first_image_url, show_flag) "
            "VALUES (:cid, 12, :t, 'http://kto.example/i.jpg', 1)"
        ),
        {"cid": content_id, "t": f"title-{content_id}"},
    )


async def _drain_pool(session: AsyncSession) -> None:
    """Empty the eligible pool within the rolled-back test transaction."""
    await session.execute(
        text(
            "UPDATE spots SET show_flag = 0 "
            "WHERE show_flag = 1 AND first_image_url IS NOT NULL AND first_image_url <> ''"
        )
    )


def test_seed_for_date_is_deterministic() -> None:
    assert _seed_for_date("2026-05-30") == _seed_for_date("2026-05-30")
    assert _seed_for_date("2026-05-30") != _seed_for_date("2026-05-31")


def test_seconds_until_kst_midnight_is_positive_and_bounded() -> None:
    kst = ZoneInfo("Asia/Seoul")
    now = datetime(2026, 5, 30, 23, 59, 0, tzinfo=kst)
    secs = _seconds_until_kst_midnight(now)
    assert 0 < secs <= 86400


@pytest.mark.asyncio
async def test_raises_resource_not_found_on_empty_pool(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(recommendations_services, "redis_cache", FakeRedis(decode_responses=False))
    await _drain_pool(db_session)
    with pytest.raises(ResourceNotFound):
        await get_today_inspo(db_session)


@pytest.mark.asyncio
async def test_returns_card_and_writes_cache(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeRedis(decode_responses=False)
    monkeypatch.setattr(recommendations_services, "redis_cache", fake)
    await _seed_spot(db_session, "rti_a")
    await _seed_spot(db_session, "rti_b")

    first = await get_today_inspo(db_session)
    second = await get_today_inspo(db_session)
    assert first.content_id == second.content_id  # deterministic / stable

    keys = await fake.keys("rec:today_inspo:*")
    assert len(keys) == 1


@pytest.mark.asyncio
async def test_cache_hit_short_circuits_db(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json

    fake = FakeRedis(decode_responses=False)
    monkeypatch.setattr(recommendations_services, "redis_cache", fake)
    today = recommendations_services._kst_now().date().isoformat()
    key = f"rec:today_inspo:{today}"
    payload = {
        "contentId": "cached_x",
        "title": "Cached Spot",
        "firstImageUrl": "http://kto.example/c.jpg",
        "addr1": "addr",
        "mapx": 127.0,
        "mapy": 37.0,
    }
    await fake.set(key, json.dumps(payload))

    card = await get_today_inspo(db_session)
    assert card.content_id == "cached_x"
    assert card.title == "Cached Spot"


@pytest.mark.asyncio
async def test_redis_failure_falls_through_to_compute(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    class BrokenRedis:
        async def get(self, *_a, **_k):
            raise RedisError("boom")

        async def set(self, *_a, **_k):
            raise RedisError("boom")

    monkeypatch.setattr(recommendations_services, "redis_cache", BrokenRedis())
    await _drain_pool(db_session)
    await _seed_spot(db_session, "rti_fallback")

    card = await get_today_inspo(db_session)  # must not raise
    assert card.content_id == "rti_fallback"
