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


def test_a_dish_place_in_the_raw_question_yields_its_canonical_title_term() -> None:
    assert retrieve.dish_search_terms("정읍 삼겹살집") == ["삼겹살"]


@pytest.mark.parametrize("question", ["정읍 맛집", "정읍 카페"])
def test_a_generic_food_question_has_no_dish_title_constraint(question: str) -> None:
    assert retrieve.dish_search_terms(question) == []


def test_an_exact_dish_word_is_not_inferred_from_an_unrelated_word() -> None:
    assert retrieve.dish_search_terms("정읍 회 맛집") == ["회"]
    assert retrieve.dish_search_terms("정읍 교회 근처") == []


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("국밥 말고 삼겹살집", ["삼겹살"]),
        ("국밥은 말고 삼겹살집", ["삼겹살"]),
        ("한국수자원공사 근처", []),
        ("삼겹살마을 근처 카페", []),
        ("국밥을 먹고 싶어", ["국밥"]),
        ("돈까스전문점 추천", ["돈까스"]),
        ("거기 근처 삼겹살집은?", ["삼겹살"]),
        ("거기 근처 보쌈집은?", ["보쌈"]),
    ],
)
def test_only_a_positively_requested_dish_becomes_a_title_term(
    question: str, expected: list[str]
) -> None:
    assert retrieve.dish_search_terms(question) == expected
