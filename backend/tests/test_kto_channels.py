"""feed festa·pets·snap 채널 — KTO fetch + 자정 Redis 캐시 단위 테스트."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date, timedelta
from unittest.mock import AsyncMock

import pytest

from app.core.kto_client import KtoClient, KtoService
from app.modules.feed.services.channels import ChannelCardRow
from app.modules.feed.services.kto_channels import (
    _bg_tasks,
    _cache_key,
    _today,
    fetch_festa_cards,
    fetch_pets_cards,
    fetch_snap_cards,
    load_kto_channel_cached,
)

TODAY = date(2026, 7, 12)

FESTA_ITEMS = [
    {
        "contentid": "F1",
        "title": "무주 반딧불 축제",
        "addr1": "전북 무주군 무주읍",
        "firstimage": "http://tong.visitkorea.or.kr/f1.jpg",
        "eventstartdate": "20260705",
        "eventenddate": "20260715",
        "cpyrhtDivCd": "Type3",
    },
    {
        "contentid": "F2",
        "title": "여수 밤바다 축제",
        "addr1": "전남 여수시 교동",
        "firstimage": "http://tong.visitkorea.or.kr/f2.jpg",
        "eventstartdate": "20260701",
        "eventenddate": "20260731",
        "cpyrhtDivCd": "Type3",
    },
]

FESTA_BAD_ROWS = [
    {
        "contentid": "F3",
        "title": "이미 끝난 축제",
        "addr1": "서울 종로구",
        "firstimage": "http://tong.visitkorea.or.kr/f3.jpg",
        "eventstartdate": "20260601",
        "eventenddate": "20260610",
    },
    {
        "contentid": "F4",
        "title": "이미지 없는 축제",
        "addr1": "부산 해운대구",
        "firstimage": "",
        "eventstartdate": "20260705",
        "eventenddate": "20260720",
    },
    {
        "contentid": "F5",
        "title": "정상 축제",
        "addr1": "강원 강릉시",
        "firstimage": "http://tong.visitkorea.or.kr/f5.jpg",
        "eventstartdate": "20260710",
        "eventenddate": "20260718",
    },
]

FESTA_FUTURE_START = [
    {
        "contentid": "F6",
        "title": "아직 시작 안 한 축제",
        "addr1": "경기 수원시 팔달구",
        "firstimage": "http://tong.visitkorea.or.kr/f6.jpg",
        "eventstartdate": "20260717",
        "eventenddate": "20260725",
        "cpyrhtDivCd": "Type3",
    },
]

PETS_ITEMS = [
    {
        "contentid": f"P{i}",
        "contenttypeid": "12",
        "title": f"반려동물 여행지 {i}",
        "addr1": "제주 제주시 애월읍",
        "firstimage": f"http://tong.visitkorea.or.kr/p{i}.jpg",
        "cpyrhtDivCd": "Type3",
    }
    for i in range(15)
]

PETS_WITH_IMAGELESS = [
    *PETS_ITEMS[:3],
    {
        "contentid": "PX",
        "contenttypeid": "12",
        "title": "이미지 없는 반려동물 여행지",
        "addr1": "서울 강남구",
        "firstimage": "",
    },
]

SNAP_ITEMS = [
    {
        "galContentId": "G1",
        "galTitle": "노을 진 통영 앞바다",
        "galWebImageUrl": "http://tong.visitkorea.or.kr/g1.jpg",
        "galPhotographyLocation": "경남 통영시",
        "galPhotographer": "홍길동",
    },
    {
        "galContentId": "G2",
        "galTitle": "가을 내장산 단풍",
        "galWebImageUrl": "http://tong.visitkorea.or.kr/g2.jpg",
        "galPhotographyLocation": "전북 정읍시",
        "galPhotographer": "김사진",
    },
]


def _kto_returning(items: list[dict]) -> KtoClient:
    kto = AsyncMock(spec=KtoClient)
    kto.call = AsyncMock(return_value=items)
    return kto


@pytest.fixture
def kto_mock() -> KtoClient:
    return _kto_returning(FESTA_ITEMS)


@pytest.fixture
def kto_mock_with_bad_rows() -> KtoClient:
    return _kto_returning(FESTA_BAD_ROWS)


@pytest.fixture
def kto_mock_pets() -> KtoClient:
    return _kto_returning(PETS_ITEMS)


@pytest.fixture
def kto_mock_snap() -> KtoClient:
    return _kto_returning(SNAP_ITEMS)


async def test_festa_cards_dday_and_line(kto_mock: KtoClient) -> None:
    cards = await fetch_festa_cards(kto_mock, today=TODAY)
    assert cards[0].content_id == "F1"
    assert cards[0].dday == "D-3"
    assert "까지" in (cards[0].line or "")
    assert cards[0].saveable is True
    assert cards[0].region_label == "전북 무주군"


async def test_festa_uses_past_window_start(kto_mock: KtoClient) -> None:
    await fetch_festa_cards(kto_mock, today=TODAY)
    _, call_kwargs = kto_mock.call.call_args
    assert call_kwargs["eventStartDate"] == "20260413"


async def test_festa_sorted_ascending_by_days_until_end(kto_mock: KtoClient) -> None:
    cards = await fetch_festa_cards(kto_mock, today=TODAY)
    assert [c.content_id for c in cards] == ["F1", "F2"]


async def test_festa_excludes_ended_and_imageless(kto_mock_with_bad_rows: KtoClient) -> None:
    cards = await fetch_festa_cards(kto_mock_with_bad_rows, today=TODAY)
    assert all(c.image_url for c in cards)
    assert [c.content_id for c in cards] == ["F5"]


async def test_festa_excludes_not_yet_started() -> None:
    kto = _kto_returning(FESTA_FUTURE_START)
    cards = await fetch_festa_cards(kto, today=TODAY)
    assert [c.content_id for c in cards] == []


async def test_festa_paginates_to_find_ongoing_on_second_page() -> None:
    page1 = [
        {
            "contentid": f"OLD{i}",
            "title": f"이미 끝난 축제 {i}",
            "addr1": "서울 종로구",
            "firstimage": f"http://tong.visitkorea.or.kr/old{i}.jpg",
            "eventstartdate": "20260401",
            "eventenddate": "20260410",
            "cpyrhtDivCd": "Type3",
        }
        for i in range(100)
    ]
    page2 = [
        {
            "contentid": "ONGOING2",
            "title": "2페이지 진행 중 축제",
            "addr1": "강원 속초시",
            "firstimage": "http://tong.visitkorea.or.kr/ongoing2.jpg",
            "eventstartdate": "20260710",
            "eventenddate": "20260716",
            "cpyrhtDivCd": "Type3",
        }
    ]

    async def _paged(*_args: object, pageNo: int = 1, **_kwargs: object) -> list[dict]:
        return {1: page1, 2: page2}.get(pageNo, [])

    kto = AsyncMock(spec=KtoClient)
    kto.call = AsyncMock(side_effect=_paged)

    cards = await fetch_festa_cards(kto, today=TODAY)

    assert [c.content_id for c in cards] == ["ONGOING2"]
    assert kto.call.await_count == 2


async def test_pets_static_tag_and_saveable(kto_mock_pets: KtoClient) -> None:
    cards = await fetch_pets_cards(kto_mock_pets)
    assert len(cards) == 10
    assert all(c.tag == "반려동물 동반 가능" for c in cards)
    assert all(c.saveable is True and c.content_id for c in cards)
    assert all(c.image_url for c in cards)


async def test_pets_excludes_imageless() -> None:
    kto = _kto_returning(PETS_WITH_IMAGELESS)
    cards = await fetch_pets_cards(kto)
    assert len(cards) == 3
    assert all(c.image_url for c in cards)


async def test_snap_cards_are_view_only(kto_mock_snap: KtoClient) -> None:
    cards = await fetch_snap_cards(kto_mock_snap)
    assert cards[0].content_id is None
    assert cards[0].saveable is False
    assert cards[0].title == "노을 진 통영 앞바다"
    assert cards[0].region_label == ""
    assert cards[0].line == "경남 통영시"


async def test_snap_upgrades_image_to_https(kto_mock_snap: KtoClient) -> None:
    cards = await fetch_snap_cards(kto_mock_snap)
    assert all((c.image_url or "").startswith("https://") for c in cards)


async def test_channel_cache_roundtrip(redis_client_fake, kto_mock_snap: KtoClient) -> None:
    first = await load_kto_channel_cached(redis_client_fake, kto_mock_snap, "snap")
    second = await load_kto_channel_cached(redis_client_fake, kto_mock_snap, "snap")
    assert first == second
    assert kto_mock_snap.call.await_count == 1


async def test_channel_serves_stale_then_refreshes_in_background(
    redis_client_fake, kto_mock_snap: KtoClient
) -> None:
    stale_card = ChannelCardRow(
        content_id=None, title="어제 카드", region_label="", image_url="x", saveable=False
    )
    stale = json.dumps(
        {"date": (_today() - timedelta(days=1)).isoformat(), "cards": [asdict(stale_card)]}
    )
    await redis_client_fake.set(_cache_key("snap"), stale)

    served = await load_kto_channel_cached(redis_client_fake, kto_mock_snap, "snap")
    assert served[0].title == "어제 카드"

    for task in list(_bg_tasks):
        await task
    assert kto_mock_snap.call.await_count == 1

    fresh = await load_kto_channel_cached(redis_client_fake, kto_mock_snap, "snap")
    assert fresh[0].title == "노을 진 통영 앞바다"
    assert kto_mock_snap.call.await_count == 1


async def test_channel_cache_fail_open_on_redis_error(kto_mock_snap: KtoClient) -> None:
    broken = AsyncMock()
    broken.get = AsyncMock(side_effect=RuntimeError("redis down"))
    broken.set = AsyncMock(side_effect=RuntimeError("redis down"))
    cards = await load_kto_channel_cached(broken, kto_mock_snap, "snap")
    assert cards[0].title == "노을 진 통영 앞바다"
    assert kto_mock_snap.call.await_count == 1


async def test_channel_cache_propagates_kto_failure(redis_client_fake) -> None:
    from app.core.exceptions import KtoApiUnavailable

    kto = AsyncMock(spec=KtoClient)
    kto.call = AsyncMock(side_effect=KtoApiUnavailable())
    with pytest.raises(KtoApiUnavailable):
        await load_kto_channel_cached(redis_client_fake, kto, "festa")


async def test_festa_calls_kor_searchfestival2(kto_mock: KtoClient) -> None:
    await fetch_festa_cards(kto_mock, today=TODAY)
    call_args, _ = kto_mock.call.call_args
    assert call_args[0] == KtoService.KOR
    assert call_args[1] == "searchFestival2"
