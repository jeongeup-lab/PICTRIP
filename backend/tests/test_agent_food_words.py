from __future__ import annotations

import pytest

from app.modules.agent.services import retrieve


@pytest.mark.parametrize(
    "keyword",
    ["맛집", "식당", "밥집", "먹거리", "삼겹살집", "국밥집", "횟집", "고깃집", "돈까스전문점"],
)
def test_a_place_to_eat_routes_to_the_food_pool(keyword: str) -> None:
    assert retrieve.food_word([keyword]) == "food"


@pytest.mark.parametrize("keyword", ["삼겹살", "국밥", "냉면", "칼국수", "파스타", "회"])
def test_a_bare_dish_still_means_the_user_wants_somewhere_to_eat(keyword: str) -> None:
    assert retrieve.food_word([keyword]) == "food"


@pytest.mark.parametrize("keyword", ["카페", "커피", "찻집", "디저트", "베이커리", "빵집"])
def test_a_place_to_drink_routes_to_the_cafe_pool(keyword: str) -> None:
    assert retrieve.food_word([keyword]) == "cafe"


@pytest.mark.parametrize("keyword", ["계곡", "박물관", "해수욕장", "전망대", "한옥마을", "수목원"])
def test_a_sightseeing_keyword_is_not_food(keyword: str) -> None:
    assert retrieve.food_word([keyword]) is None


@pytest.mark.parametrize("keyword", ["교회", "전시회", "박람회", "미술관회관", "고기잡이체험"])
def test_a_word_that_merely_contains_a_dish_syllable_is_not_food(keyword: str) -> None:
    assert retrieve.food_word([keyword]) is None


def test_mixing_food_and_sightseeing_picks_neither_so_the_normal_search_runs() -> None:
    assert retrieve.food_word(["맛집", "계곡"]) is None


def test_mixing_food_and_cafe_picks_neither() -> None:
    assert retrieve.food_word(["맛집", "카페"]) is None


def test_no_keywords_is_not_food() -> None:
    assert retrieve.food_word([]) is None
