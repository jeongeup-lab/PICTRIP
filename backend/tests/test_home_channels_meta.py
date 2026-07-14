"""GET /v1/home/channels — 채널 메타 목록 조립 (fail-soft)."""

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
from app.core.kto_client import get_kto
from app.core.redis import get_redis
from app.main import app

_FESTA_ITEM = {
    "contentid": "F1",
    "title": "무주 반딧불 축제",
    "addr1": "전북 무주군 무주읍",
    "firstimage": "http://tong.visitkorea.or.kr/f1.jpg",
    "eventstartdate": "20260101",
    "eventenddate": "20991231",
}
_PETS_ITEM = {
    "contentid": "P1",
    "title": "반려견 동반 카페",
    "addr1": "서울 강남구",
    "firstimage": "http://tong.visitkorea.or.kr/p1.jpg",
}
_SNAP_ITEM = {
    "galTitle": "가을 통영",
    "galPhotographyLocation": "경남 통영시",
    "galWebImageUrl": "http://tong.visitkorea.or.kr/s1.jpg",
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


async def _seed_concentration(session: AsyncSession, cid: str, *, rate: str, overview: str) -> None:
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, first_image_url, "
            "show_flag, ldong_regn_cd, ldong_signgu_cd, lcls_systm1) "
            "VALUES (:cid, 12, :t, 'http://kto/i.jpg', 1, '26', '26380', 'NA')"
        ),
        {"cid": cid, "t": f"t-{cid}"},
    )
    await session.execute(
        text(
            "INSERT INTO spot_concentration "
            "(content_id, concentration_rate, base_ymd, raw_name) "
            "VALUES (:cid, :rate, DATE '2026-07-01', :rn)"
        ),
        {"cid": cid, "rate": rate, "rn": f"n-{cid}"},
    )
    await session.execute(
        text(
            "INSERT INTO spot_details (content_id, content_type_id, overview) "
            "VALUES (:cid, 12, :ov)"
        ),
        {"cid": cid, "ov": overview},
    )


@pytest_asyncio.fixture
async def seeded_concentration(db_session: AsyncSession) -> None:
    await _seed_region(db_session)
    await _seed_concentration(db_session, "c90", rate="90.00", overview="설명 90")
    await _seed_concentration(db_session, "c60", rate="60.00", overview="설명 60")
    await _seed_concentration(db_session, "c10", rate="10.00", overview="설명 10")
    await db_session.flush()


def _install(db_session: AsyncSession, kto: object) -> None:
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_redis] = lambda: FakeRedis(decode_responses=True)
    app.dependency_overrides[get_kto] = lambda: kto


@pytest_asyncio.fixture
async def kto_all_mocked(db_session: AsyncSession) -> AsyncIterator[None]:
    async def _call(service: object, method: str, **_: Any) -> list[dict[str, Any]]:
        if method == "searchFestival2":
            return [_FESTA_ITEM]
        if method == "areaBasedList2":
            return [_PETS_ITEM]
        if method == "galleryList1":
            return [_SNAP_ITEM]
        return []

    kto = AsyncMock()
    kto.call = AsyncMock(side_effect=_call)
    _install(db_session, kto)
    yield
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def kto_festa_empty(db_session: AsyncSession) -> AsyncIterator[None]:
    async def _call(service: object, method: str, **_: Any) -> list[dict[str, Any]]:
        if method == "searchFestival2":
            return []
        if method == "areaBasedList2":
            return [_PETS_ITEM]
        if method == "galleryList1":
            return [_SNAP_ITEM]
        return []

    kto = AsyncMock()
    kto.call = AsyncMock(side_effect=_call)
    _install(db_session, kto)
    yield
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def kto_broken(db_session: AsyncSession) -> AsyncIterator[None]:
    async def _call(service: object, method: str, **_: Any) -> list[dict[str, Any]]:
        raise RuntimeError("KTO down")

    kto = AsyncMock()
    kto.call = AsyncMock(side_effect=_call)
    _install(db_session, kto)
    yield
    app.dependency_overrides.clear()


async def test_channels_meta_order_and_shape(client, seeded_concentration, kto_all_mocked) -> None:
    res = await client.get("/v1/home/channels")
    assert res.status_code == 200
    chans = res.json()["data"]["channels"]
    assert [c["key"] for c in chans] == ["around", "hot", "hidden", "festa", "pets", "snap"]
    assert chans[0]["thumbnailUrl"] is None
    assert chans[0]["available"] is True
    assert chans[1]["thumbnailUrl"] == "http://kto/i.jpg"
    by_key = {c["key"]: c for c in chans}
    assert by_key["festa"]["available"] is True
    assert by_key["festa"]["thumbnailUrl"] == "https://tong.visitkorea.or.kr/f1.jpg"
    assert by_key["pets"]["thumbnailUrl"] == "https://tong.visitkorea.or.kr/p1.jpg"
    assert by_key["snap"]["thumbnailUrl"] == "https://tong.visitkorea.or.kr/s1.jpg"
    assert by_key["snap"]["label"] == "Snap"


async def test_channels_meta_sets_short_edge_cache_header(
    client, seeded_concentration, kto_all_mocked
) -> None:
    res = await client.get("/v1/home/channels")
    assert res.status_code == 200
    assert res.headers["cache-control"] == "public, s-maxage=600"


async def test_channel_cards_endpoint_is_not_edge_cached(
    client, seeded_concentration, kto_all_mocked
) -> None:
    res = await client.get("/v1/home/channels/festa")
    assert res.status_code == 200
    assert "cache-control" not in res.headers


async def test_channels_meta_hides_festa_when_empty(
    client, seeded_concentration, kto_festa_empty
) -> None:
    chans = (await client.get("/v1/home/channels")).json()["data"]["channels"]
    keys = [c["key"] for c in chans]
    assert "festa" not in keys
    assert keys == ["around", "hot", "hidden", "pets", "snap"]


@pytest_asyncio.fixture
async def kto_slow_pets(db_session: AsyncSession) -> AsyncIterator[None]:
    async def _call(service: object, method: str, **_: Any) -> list[dict[str, Any]]:
        if method == "searchFestival2":
            return [_FESTA_ITEM]
        if method == "areaBasedList2":
            await asyncio.sleep(0.3)
            return [_PETS_ITEM]
        if method == "galleryList1":
            return [_SNAP_ITEM]
        return []

    kto = AsyncMock()
    kto.call = AsyncMock(side_effect=_call)
    _install(db_session, kto)
    yield
    app.dependency_overrides.clear()


async def test_channels_meta_times_out_slow_channel(
    client, seeded_concentration, kto_slow_pets, monkeypatch
) -> None:
    monkeypatch.setattr("app.modules.feed.services.channels._META_TIMEOUT", 0.05)
    chans = (await client.get("/v1/home/channels")).json()["data"]["channels"]
    by_key = {c["key"]: c for c in chans}
    assert by_key["pets"]["available"] is False
    assert by_key["snap"]["thumbnailUrl"] is not None
    assert by_key["festa"]["available"] is True


async def test_channels_meta_degrades_on_kto_error(
    client, seeded_concentration, kto_broken
) -> None:
    res = await client.get("/v1/home/channels")
    assert res.status_code == 200
    by_key = {c["key"]: c for c in res.json()["data"]["channels"]}
    assert by_key["pets"]["available"] is False
    assert by_key["pets"]["thumbnailUrl"] is None
    assert by_key["snap"]["available"] is False
    assert by_key["festa"]["available"] is False
    assert by_key["hot"]["available"] is True
    assert by_key["hot"]["thumbnailUrl"] == "http://kto/i.jpg"
    assert by_key["hidden"]["available"] is True
    assert by_key["hidden"]["thumbnailUrl"] == "http://kto/i.jpg"
