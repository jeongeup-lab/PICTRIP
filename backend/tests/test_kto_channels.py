from __future__ import annotations

import asyncio
import json
from dataclasses import asdict
from datetime import date, timedelta
from unittest.mock import AsyncMock

import pytest

from app.kto.client import KtoClient, KtoService
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
from app.web.errors import KtoApiUnavailable

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


async def test_pets_requests_attractions_only(kto_mock_pets: KtoClient) -> None:
    await fetch_pets_cards(kto_mock_pets)
    _, call_kwargs = kto_mock_pets.call.call_args
    assert call_kwargs["contentTypeId"] == 12


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
    from app.web.errors import KtoApiUnavailable

    kto = AsyncMock(spec=KtoClient)
    kto.call = AsyncMock(side_effect=KtoApiUnavailable())
    with pytest.raises(KtoApiUnavailable):
        await load_kto_channel_cached(redis_client_fake, kto, "festa")


async def test_festa_calls_kor_searchfestival2(kto_mock: KtoClient) -> None:
    await fetch_festa_cards(kto_mock, today=TODAY)
    call_args, _ = kto_mock.call.call_args
    assert call_args[0] == KtoService.KOR
    assert call_args[1] == "searchFestival2"


async def test_warm_all_channels_populates_every_key(
    redis_client_fake, kto_mock_snap: KtoClient
) -> None:
    from app.modules.feed.services.kto_channels import warm_all_channels

    await warm_all_channels(redis_client_fake, kto_mock_snap)

    for key in ("festa", "pets", "snap"):
        raw = await redis_client_fake.get(_cache_key(key))
        assert raw is not None
        assert json.loads(raw)["date"] == _today().isoformat()


async def test_warm_all_channels_is_fail_soft_per_channel(redis_client_fake) -> None:
    from app.modules.feed.services.kto_channels import warm_all_channels

    async def _call(service: object, operation: object, *_a: object, **_k: object) -> list[dict]:
        if "Festival" in str(operation):
            raise RuntimeError("kto down")
        return SNAP_ITEMS

    kto = AsyncMock(spec=KtoClient)
    kto.call = AsyncMock(side_effect=_call)

    result = await warm_all_channels(redis_client_fake, kto)

    assert result["festa"] is False
    assert result["snap"] is True
    assert await redis_client_fake.get(_cache_key("festa")) is None
    assert await redis_client_fake.get(_cache_key("snap")) is not None


FESTIVAL_POOL_ITEMS = [
    {
        "contentid": str(i),
        "title": f"축제{i}",
        "addr1": "제주특별자치도 서귀포시 1" if i == 0 else "서울특별시 종로구 1",
        "firstimage": "https://kto/i.jpg",
        "eventstartdate": "20260701",
        "eventenddate": "20260810",
    }
    for i in range(30)
]


class _PagedKto:
    def __init__(self, items: list[dict]) -> None:
        self.items = items

    async def call(self, service: object, operation: object, **params: object) -> list[dict]:
        return self.items if params["pageNo"] == 1 else []


async def test_festival_pool_returns_more_than_the_channel_and_caches_separately(
    redis_client_fake, monkeypatch
) -> None:
    from app.modules.feed.services import kto_channels

    monkeypatch.setattr(kto_channels, "_today", lambda: TODAY)

    pool = await kto_channels.load_festival_pool(redis_client_fake, _PagedKto(FESTIVAL_POOL_ITEMS))

    assert len(pool) == 30
    assert await redis_client_fake.get("festival:pool:v2") is not None


def _running_festival_item(index: int) -> dict:
    return {
        "contentid": str(index),
        "title": f"축제{index}",
        "addr1": "제주특별자치도 서귀포시 1" if index == 79 else "서울특별시 종로구 1",
        "firstimage": "https://kto/i.jpg",
        "eventstartdate": (TODAY - timedelta(days=1)).strftime("%Y%m%d"),
        "eventenddate": (TODAY + timedelta(days=index)).strftime("%Y%m%d"),
    }


async def test_festival_pool_keeps_every_running_festival_not_just_the_first_sixty(
    redis_client_fake, monkeypatch
) -> None:
    from app.modules.feed.services import kto_channels

    monkeypatch.setattr(kto_channels, "_today", lambda: TODAY)
    items = [_running_festival_item(i) for i in range(80)]

    pool = await kto_channels.load_festival_pool(redis_client_fake, _PagedKto(items))

    assert len(pool) == 80
    assert any("제주" in card.region_label for card in pool)


async def test_festival_pool_second_call_is_served_from_cache(
    redis_client_fake, monkeypatch
) -> None:
    from app.modules.feed.services import kto_channels

    monkeypatch.setattr(kto_channels, "_today", lambda: TODAY)
    kto = AsyncMock(spec=KtoClient)
    kto.call = AsyncMock(return_value=FESTIVAL_POOL_ITEMS)

    first = await kto_channels.load_festival_pool(redis_client_fake, kto)
    after_first = kto.call.await_count
    second = await kto_channels.load_festival_pool(redis_client_fake, kto)

    assert first == second
    assert kto.call.await_count == after_first


async def test_festa_channel_still_caps_at_ten_cards() -> None:
    cards = await fetch_festa_cards(_PagedKto(FESTIVAL_POOL_ITEMS), today=TODAY)

    assert len(cards) == 10


class _FestivalApi:
    def __init__(self, items: list[dict]) -> None:
        self.items = items
        self.params: list[dict] = []

    async def call(self, service: object, operation: object, **params: object) -> list[dict]:
        self.params.append(params)
        window = str(params["eventStartDate"])
        rows = int(str(params["numOfRows"]))
        page = int(str(params["pageNo"]))
        matched = [it for it in self.items if str(it["eventstartdate"]) >= window]
        offset = (page - 1) * rows
        return matched[offset : offset + rows]


def _festival(
    content_id: str, *, started_days_ago: int, ends_in_days: int, addr: str = "서울특별시 종로구 1"
) -> dict:
    return {
        "contentid": content_id,
        "title": f"축제 {content_id}",
        "addr1": addr,
        "firstimage": "https://kto/i.jpg",
        "eventstartdate": (TODAY - timedelta(days=started_days_ago)).strftime("%Y%m%d"),
        "eventenddate": (TODAY + timedelta(days=ends_in_days)).strftime("%Y%m%d"),
    }


async def test_festival_pool_keeps_long_running_festival_started_before_channel_window(
    redis_client_fake, monkeypatch
) -> None:
    from app.modules.feed.services import kto_channels

    monkeypatch.setattr(kto_channels, "_today", lambda: TODAY)
    api = _FestivalApi(
        [
            _festival("LONG", started_days_ago=200, ends_in_days=5),
            _festival("SHORT", started_days_ago=2, ends_in_days=1),
        ]
    )

    pool = await kto_channels.load_festival_pool(redis_client_fake, api)

    assert {card.content_id for card in pool} == {"LONG", "SHORT"}
    assert api.params[0]["eventStartDate"] == (TODAY - timedelta(days=365)).strftime("%Y%m%d")


async def test_festival_pool_excludes_festival_that_already_ended(
    redis_client_fake, monkeypatch
) -> None:
    from app.modules.feed.services import kto_channels

    monkeypatch.setattr(kto_channels, "_today", lambda: TODAY)
    api = _FestivalApi(
        [
            _festival("ENDED", started_days_ago=200, ends_in_days=-1),
            _festival("RUNNING", started_days_ago=200, ends_in_days=2),
        ]
    )

    pool = await kto_channels.load_festival_pool(redis_client_fake, api)

    assert [card.content_id for card in pool] == ["RUNNING"]


async def test_festival_pool_drains_past_the_channel_page_budget(
    redis_client_fake, monkeypatch
) -> None:
    from app.modules.feed.services import kto_channels

    monkeypatch.setattr(kto_channels, "_today", lambda: TODAY)
    api = _FestivalApi(
        [_festival(f"R{i}", started_days_ago=200, ends_in_days=1 + i % 30) for i in range(1600)]
    )

    pool = await kto_channels.load_festival_pool(redis_client_fake, api)

    assert len(pool) == 1600


async def test_festa_channel_keeps_its_ninety_day_window_and_page_size() -> None:
    api = _FestivalApi([_festival("C1", started_days_ago=2, ends_in_days=3)])

    cards = await fetch_festa_cards(api, today=TODAY)

    assert [card.content_id for card in cards] == ["C1"]
    assert api.params[0]["eventStartDate"] == "20260413"
    assert api.params[0]["numOfRows"] == 100
    assert len(api.params) == 1


async def test_festival_pool_serves_yesterdays_cards_when_kto_is_down(
    redis_client_fake, monkeypatch
) -> None:
    from app.modules.feed.services import kto_channels

    monkeypatch.setattr(kto_channels, "_today", lambda: TODAY - timedelta(days=1))
    kto = AsyncMock(spec=KtoClient)
    kto.call = AsyncMock(return_value=FESTIVAL_POOL_ITEMS)
    yesterday = await kto_channels.load_festival_pool(redis_client_fake, kto)
    assert yesterday

    monkeypatch.setattr(kto_channels, "_today", lambda: TODAY)
    kto.call = AsyncMock(side_effect=KtoApiUnavailable())

    served = await kto_channels.load_festival_pool(redis_client_fake, kto)

    assert [card.content_id for card in served] == [card.content_id for card in yesterday]


async def test_festival_pool_reraises_when_kto_is_down_and_nothing_is_cached(
    redis_client_fake, monkeypatch
) -> None:
    from app.modules.feed.services import kto_channels

    monkeypatch.setattr(kto_channels, "_today", lambda: TODAY)
    kto = AsyncMock(spec=KtoClient)
    kto.call = AsyncMock(side_effect=KtoApiUnavailable())

    with pytest.raises(KtoApiUnavailable):
        await kto_channels.load_festival_pool(redis_client_fake, kto)


async def test_festival_pool_fetch_timeout_falls_back_to_the_stale_cache(
    redis_client_fake, monkeypatch
) -> None:
    from app.modules.feed.services import kto_channels

    monkeypatch.setattr(kto_channels, "_today", lambda: TODAY - timedelta(days=1))
    kto = AsyncMock(spec=KtoClient)
    kto.call = AsyncMock(return_value=FESTIVAL_POOL_ITEMS)
    yesterday = await kto_channels.load_festival_pool(redis_client_fake, kto)

    monkeypatch.setattr(kto_channels, "_today", lambda: TODAY)

    async def never(*args: object, **kwargs: object) -> list[ChannelCardRow]:
        await asyncio.sleep(30)
        return []

    monkeypatch.setattr(kto_channels, "fetch_festival_pool_cards", never)

    served = await kto_channels.load_festival_pool(redis_client_fake, kto, fetch_timeout=0.01)

    assert [card.content_id for card in served] == [card.content_id for card in yesterday]


async def test_festival_pool_fetch_timeout_surfaces_when_nothing_is_cached(
    redis_client_fake, monkeypatch
) -> None:
    from app.modules.feed.services import kto_channels

    monkeypatch.setattr(kto_channels, "_today", lambda: TODAY)

    async def never(*args: object, **kwargs: object) -> list[ChannelCardRow]:
        await asyncio.sleep(30)
        return []

    monkeypatch.setattr(kto_channels, "fetch_festival_pool_cards", never)

    with pytest.raises(TimeoutError):
        await kto_channels.load_festival_pool(
            redis_client_fake, AsyncMock(spec=KtoClient), fetch_timeout=0.01
        )


async def test_stale_festival_cards_are_rescored_against_today(
    redis_client_fake, monkeypatch
) -> None:
    from app.modules.feed.services import kto_channels

    monkeypatch.setattr(kto_channels, "_today", lambda: TODAY)
    kto = AsyncMock(spec=KtoClient)
    kto.call = AsyncMock(return_value=FESTIVAL_POOL_ITEMS)
    fresh = {c.content_id: c for c in await kto_channels.load_festival_pool(redis_client_fake, kto)}
    assert fresh

    monkeypatch.setattr(kto_channels, "_today", lambda: TODAY + timedelta(days=1))
    kto.call = AsyncMock(side_effect=KtoApiUnavailable())

    served = await kto_channels.load_festival_pool(redis_client_fake, kto)

    assert served
    for card in served:
        assert int(card.dday[2:]) == int(fresh[card.content_id].dday[2:]) - 1


async def test_a_festival_that_already_ended_is_dropped_from_the_stale_pool(
    redis_client_fake, monkeypatch
) -> None:
    from app.modules.feed.services import kto_channels

    items = [
        {
            "contentid": "short",
            "title": "곧 끝나는 축제",
            "addr1": "서울특별시 종로구 1",
            "firstimage": "https://kto/i.jpg",
            "eventstartdate": "20260701",
            "eventenddate": "20260713",
        },
        {
            "contentid": "long",
            "title": "오래 하는 축제",
            "addr1": "서울특별시 종로구 2",
            "firstimage": "https://kto/i.jpg",
            "eventstartdate": "20260701",
            "eventenddate": "20260810",
        },
    ]
    monkeypatch.setattr(kto_channels, "_today", lambda: TODAY)
    kto = AsyncMock(spec=KtoClient)
    kto.call = AsyncMock(return_value=items)
    fresh = await kto_channels.load_festival_pool(redis_client_fake, kto)
    assert {c.content_id for c in fresh} == {"short", "long"}

    monkeypatch.setattr(kto_channels, "_today", lambda: TODAY + timedelta(days=2))
    kto.call = AsyncMock(side_effect=KtoApiUnavailable())

    served = await kto_channels.load_festival_pool(redis_client_fake, kto)

    assert [c.content_id for c in served] == ["long"]
    assert served[0].dday == "D-27"
    assert served[0].line.startswith("8월 10일까지")


async def test_the_festival_cache_outlives_a_full_day_so_stale_can_cover_it(
    redis_client_fake, monkeypatch
) -> None:
    from app.modules.feed.services import kto_channels

    monkeypatch.setattr(kto_channels, "_today", lambda: TODAY)
    kto = AsyncMock(spec=KtoClient)
    kto.call = AsyncMock(return_value=FESTIVAL_POOL_ITEMS)
    await kto_channels.load_festival_pool(redis_client_fake, kto)

    ttl = await redis_client_fake.ttl(kto_channels._FESTIVAL_POOL_KEY)

    assert ttl > 86_400
