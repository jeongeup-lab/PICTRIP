from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agent.services import geocode as geocode_service
from app.modules.agent.services import landmarks
from app.modules.spots.services import SpotSearchRow


def _row(content_id: str, title: str, addr1: str, lat: float, lng: float) -> SpotSearchRow:
    return SpotSearchRow(
        content_id=content_id,
        title=title,
        addr1=addr1,
        lat=lat,
        lng=lng,
        image_url=None,
        cpyrht_div_cd=None,
        category=None,
        content_type_id=12,
        similarity=1.0,
    )


SEOUL_STATION_ROOF = _row("1", "서울역 옥상정원(The Roof)", "서울특별시 중구", 37.5561, 126.9723)
JEONGEUP_STATION = _row("2", "정읍역 (고속철도)", "전북특별자치도 정읍시", 35.5719, 126.8556)
GAMCHEON = _row("3", "감천문화마을", "부산광역시 사하구", 35.0975, 129.0107)


@pytest.mark.parametrize(
    ("asked", "found"),
    [
        ("감천문화마을", "감천문화마을"),
        ("정읍역", "정읍역 (고속철도)"),
        ("내장사", "내장사(정읍)"),
        ("오동도", " 오동도 "),
    ],
)
def test_a_title_that_is_the_asked_name_once_qualifiers_are_stripped_is_exact(
    asked: str, found: str
) -> None:
    assert geocode_service.names_match_exactly(asked, found) is True


@pytest.mark.parametrize(
    ("asked", "found"),
    [
        ("서울역", "서울역 옥상정원(The Roof)"),
        ("수원역", "수원역전시장"),
        ("대천역", "대천역 장항선"),
        ("", "아무거나"),
    ],
)
def test_a_title_that_merely_starts_with_the_asked_name_is_not_exact(
    asked: str, found: str
) -> None:
    assert geocode_service.names_match_exactly(asked, found) is False


@pytest.mark.parametrize("name", ["서울역", "수원역", "동서울터미널", "김포공항"])
def test_transit_names_are_landmarks(name: str) -> None:
    assert landmarks.is_landmark(name) is True


@pytest.mark.parametrize("name", ["감천문화마을", "내장사", "지역", "관광지역"])
def test_ordinary_places_are_not_landmarks(name: str) -> None:
    assert landmarks.is_landmark(name) is False


async def test_an_exact_kto_hit_wins_without_asking_naver(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_search(session, query, *, region_hint=None, limit=3):  # type: ignore[no-untyped-def]
        return [JEONGEUP_STATION]

    async def fail_naver(asked, terms):  # type: ignore[no-untyped-def]
        raise AssertionError("naver must not be consulted for an exact hit")

    monkeypatch.setattr(geocode_service, "search_spots_by_title", fake_search)
    monkeypatch.setattr(geocode_service, "_borrow_coords_from_naver", fail_naver)

    found = await geocode_service.locate(db_session, "정읍역")

    assert found is not None
    assert found.source == "kto"
    assert found.content_id == "2"


async def test_a_station_that_only_partially_matches_asks_naver_before_settling(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_search(session, query, *, region_hint=None, limit=3):  # type: ignore[no-untyped-def]
        return [SEOUL_STATION_ROOF]

    async def fake_naver(asked, terms):  # type: ignore[no-untyped-def]
        return geocode_service.Located(
            title=asked, lat=37.5547, lng=126.9706, source="naver", content_id=None
        )

    monkeypatch.setattr(geocode_service, "search_spots_by_title", fake_search)
    monkeypatch.setattr(geocode_service, "_borrow_coords_from_naver", fake_naver)

    found = await geocode_service.locate(db_session, "서울역")

    assert found is not None
    assert found.source == "naver"
    assert found.title == "서울역"


async def test_a_station_falls_back_to_the_partial_kto_hit_when_naver_has_nothing(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_search(session, query, *, region_hint=None, limit=3):  # type: ignore[no-untyped-def]
        return [SEOUL_STATION_ROOF]

    async def empty_naver(asked, terms):  # type: ignore[no-untyped-def]
        return None

    monkeypatch.setattr(geocode_service, "search_spots_by_title", fake_search)
    monkeypatch.setattr(geocode_service, "_borrow_coords_from_naver", empty_naver)

    found = await geocode_service.locate(db_session, "서울역")

    assert found is not None
    assert found.source == "kto"
    assert found.content_id == "1"


async def test_an_ordinary_place_does_not_pay_the_naver_round_trip_for_a_partial_hit(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    partial = _row("9", "감천문화마을 전망대", "부산광역시 사하구", 35.0975, 129.0107)
    calls: list[Any] = []

    async def fake_search(session, query, *, region_hint=None, limit=3):  # type: ignore[no-untyped-def]
        return [partial]

    async def counted_naver(asked, terms):  # type: ignore[no-untyped-def]
        calls.append(asked)
        return None

    monkeypatch.setattr(geocode_service, "search_spots_by_title", fake_search)
    monkeypatch.setattr(geocode_service, "_borrow_coords_from_naver", counted_naver)

    found = await geocode_service.locate(db_session, "감천문화마을")

    assert found is not None
    assert found.content_id == "9"
    assert calls == []


async def test_nothing_anywhere_is_still_a_miss(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def empty_search(session, query, *, region_hint=None, limit=3):  # type: ignore[no-untyped-def]
        return []

    async def empty_naver(asked, terms):  # type: ignore[no-untyped-def]
        return None

    monkeypatch.setattr(geocode_service, "search_spots_by_title", empty_search)
    monkeypatch.setattr(geocode_service, "_borrow_coords_from_naver", empty_naver)

    assert await geocode_service.locate(db_session, "없는곳") is None
