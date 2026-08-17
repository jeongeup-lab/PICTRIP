from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock

import pytest_asyncio
from fakeredis.aioredis import FakeRedis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.redis import get_redis
from app.kto.client import get_kto
from app.main import app

_FESTA_ITEM = {
    "contentid": "F1",
    "title": "무주 반딧불 축제",
    "addr1": "전북 무주군 무주읍",
    "firstimage": "http://tong.visitkorea.or.kr/f1.jpg",
    "eventstartdate": "20260101",
    "eventenddate": "20991231",
}


async def _seed_region(session: AsyncSession) -> None:
    await session.execute(
        text(
            "INSERT INTO regions (ldong_regn_cd, ldong_regn_nm) VALUES (:c, :n) "
            "ON CONFLICT DO NOTHING"
        ),
        {"c": "26", "n": "부산광역시"},
    )
    await session.execute(
        text(
            "INSERT INTO sigungus (ldong_signgu_cd, ldong_regn_cd, ldong_signgu_nm) "
            "VALUES (:c, :r, :n) ON CONFLICT DO NOTHING"
        ),
        {"c": "26380", "r": "26", "n": "사하구"},
    )


async def _seed_signal_spot(
    session: AsyncSession,
    cid: str,
    *,
    image: str,
    lcls1: str = "NA",
    lcls2: str | None = None,
    photo_type: str = "view",
    aesthetic: float = 0.1,
    recent: float = 1.0,
    blog_total: int = 5000,
) -> None:
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, first_image_url, "
            "show_flag, ldong_regn_cd, ldong_signgu_cd, lcls_systm1, lcls_systm2) "
            "VALUES (:cid, 12, :t, :img, 1, '26', '26380', :l1, :l2)"
        ),
        {"cid": cid, "t": f"t-{cid}", "img": image, "l1": lcls1, "l2": lcls2},
    )
    await session.execute(
        text(
            "INSERT INTO spot_visual (content_id, photo_type, aesthetic_score) "
            "VALUES (:cid, :pt, :sc)"
        ),
        {"cid": cid, "pt": photo_type, "sc": aesthetic},
    )
    await session.execute(
        text(
            "INSERT INTO spot_buzz "
            "(content_id, scope, mentions, distinct_blogs, recent_ratio, blog_total) "
            "VALUES (:cid, 'base', 0, 0, :r, :t)"
        ),
        {"cid": cid, "r": recent, "t": blog_total},
    )


@pytest_asyncio.fixture
async def seeded_signals(db_session: AsyncSession) -> None:
    await _seed_region(db_session)
    await _seed_signal_spot(db_session, "s1", image="http://kto/spot.jpg")
    await _seed_signal_spot(
        db_session,
        "c1",
        image="http://kto/cafe.jpg",
        lcls1="FD",
        lcls2="FD05",
        photo_type="interior",
    )
    await _seed_signal_spot(
        db_session,
        "f1",
        image="http://kto/food.jpg",
        lcls1="FD",
        lcls2="FD01",
        photo_type="food",
    )
    await db_session.flush()


def _install(db_session: AsyncSession, kto: object) -> None:
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_redis] = lambda: FakeRedis(decode_responses=True)
    app.dependency_overrides[get_kto] = lambda: kto


def _kto(side_effect: Any) -> AsyncMock:
    kto = AsyncMock()
    kto.call = AsyncMock(side_effect=side_effect)
    return kto


@pytest_asyncio.fixture
async def kto_festa_ok(db_session: AsyncSession) -> AsyncIterator[None]:
    async def _call(service: object, method: str, **_: Any) -> list[dict[str, Any]]:
        return [_FESTA_ITEM] if method == "searchFestival2" else []

    _install(db_session, _kto(_call))
    yield
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def kto_festa_empty(db_session: AsyncSession) -> AsyncIterator[None]:
    async def _call(service: object, method: str, **_: Any) -> list[dict[str, Any]]:
        return []

    _install(db_session, _kto(_call))
    yield
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def kto_broken(db_session: AsyncSession) -> AsyncIterator[None]:
    async def _call(service: object, method: str, **_: Any) -> list[dict[str, Any]]:
        raise RuntimeError("KTO down")

    _install(db_session, _kto(_call))
    yield
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def kto_slow_festa(db_session: AsyncSession) -> AsyncIterator[None]:
    async def _call(service: object, method: str, **_: Any) -> list[dict[str, Any]]:
        await asyncio.sleep(0.3)
        return [_FESTA_ITEM]

    _install(db_session, _kto(_call))
    yield
    app.dependency_overrides.clear()


async def test_channels_meta_order_and_shape(client, seeded_signals, kto_festa_ok) -> None:
    res = await client.get("/v1/home/channels")
    assert res.status_code == 200
    chans = res.json()["data"]["channels"]
    assert [c["key"] for c in chans] == ["spot", "cafe", "food", "festa", "hidden"]
    by_key = {c["key"]: c for c in chans}
    assert by_key["spot"]["label"] == "SPOT"
    assert by_key["spot"]["available"] is True
    assert by_key["spot"]["thumbnailUrl"] == "http://kto/spot.jpg"
    assert by_key["cafe"]["thumbnailUrl"] == "http://kto/cafe.jpg"
    assert by_key["food"]["thumbnailUrl"] == "http://kto/food.jpg"
    assert by_key["festa"]["thumbnailUrl"] == "https://tong.visitkorea.or.kr/f1.jpg"
    assert by_key["hidden"]["available"] is True


async def test_channels_meta_sets_short_edge_cache_header(
    client, seeded_signals, kto_festa_ok
) -> None:
    res = await client.get("/v1/home/channels")
    assert res.status_code == 200
    assert res.headers["cache-control"] == "public, s-maxage=600"


async def test_channel_cards_endpoint_is_not_edge_cached(
    client, seeded_signals, kto_festa_ok
) -> None:
    res = await client.get("/v1/home/channels/festa")
    assert res.status_code == 200
    assert "cache-control" not in res.headers


async def test_channels_meta_hides_festa_when_empty(
    client, seeded_signals, kto_festa_empty
) -> None:
    chans = (await client.get("/v1/home/channels")).json()["data"]["channels"]
    keys = [c["key"] for c in chans]
    assert "festa" not in keys
    assert keys == ["spot", "cafe", "food", "hidden"]


async def test_channels_meta_times_out_slow_festa(
    client, seeded_signals, kto_slow_festa, monkeypatch
) -> None:
    monkeypatch.setattr("app.modules.feed.services.channels._META_TIMEOUT", 0.05)
    chans = (await client.get("/v1/home/channels")).json()["data"]["channels"]
    by_key = {c["key"]: c for c in chans}
    assert by_key["festa"]["available"] is False
    assert by_key["spot"]["available"] is True


async def test_channels_meta_degrades_on_kto_error(client, seeded_signals, kto_broken) -> None:
    res = await client.get("/v1/home/channels")
    assert res.status_code == 200
    by_key = {c["key"]: c for c in res.json()["data"]["channels"]}
    assert by_key["festa"]["available"] is False
    assert by_key["festa"]["thumbnailUrl"] is None
    assert by_key["spot"]["available"] is True
    assert by_key["cafe"]["available"] is True
    assert by_key["hidden"]["available"] is True
