from __future__ import annotations

import pytest

from app.modules.agent.services import intent as intent_service


@pytest.mark.parametrize(
    ("question", "landmark"),
    [
        ("서울역 근처 맛집", "서울역"),
        ("수원역 카페", "수원역"),
        ("동대구역 주변 밥집", "동대구역"),
        ("광주송정역 근처", "광주송정역"),
        ("김포공항 근처 카페", "김포공항"),
        ("동서울터미널 근처 맛집", "동서울터미널"),
    ],
)
def test_a_station_or_airport_becomes_the_place_to_search_around(
    question: str, landmark: str
) -> None:
    guessed = intent_service.fallback_intent(question)
    assert [place.name for place in guessed.namedPlaces] == [landmark]
    assert landmark not in guessed.regionHints


def test_a_landmark_does_not_swallow_the_food_keyword() -> None:
    guessed = intent_service.fallback_intent("서울역 근처 맛집")
    assert guessed.categoryKeywords == ["맛집"]
    assert guessed.nearMe is True


@pytest.mark.parametrize("question", ["지역 추천", "관광지역 알려줘", "권역별 명소"])
def test_a_word_that_merely_ends_in_the_station_syllable_is_not_a_landmark(
    question: str,
) -> None:
    assert intent_service.fallback_intent(question).namedPlaces == []


def test_a_plain_region_is_still_a_region_and_not_a_landmark() -> None:
    guessed = intent_service.fallback_intent("정읍 삼겹살집")
    assert guessed.namedPlaces == []
    assert guessed.regionHints == ["정읍", "삼겹살집"]
