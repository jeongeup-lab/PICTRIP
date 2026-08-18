from __future__ import annotations

import pytest

from app.modules.agent.schemas import QueryIntent
from app.modules.agent.services import guard


def test_self_hunger_turns_a_smalltalk_reading_into_a_food_search() -> None:
    corrected = guard.apply_corrections(QueryIntent(task="smalltalk"), "아 배고파")

    assert corrected.task == "search"
    assert corrected.categoryKeywords[0] == "맛집"


def test_asking_the_assistant_about_eating_stays_smalltalk() -> None:
    corrected = guard.apply_corrections(QueryIntent(task="smalltalk"), "너 밥 먹었어?")

    assert corrected.task == "smalltalk"
    assert corrected.categoryKeywords == []


def test_hunger_alongside_another_place_type_leaves_the_model_reading_alone() -> None:
    asked = QueryIntent(task="search", categoryKeywords=["박물관"])

    corrected = guard.apply_corrections(asked, "배고픈데 경주 박물관 갈까")

    assert corrected.categoryKeywords == ["박물관"]


def test_a_guessed_intent_still_gets_the_food_correction_without_a_task_signal() -> None:
    """폴백은 task 를 못 정한다 — 그 경로에서도 배고픔은 맛집이어야 한다."""
    corrected = guard.apply_corrections(QueryIntent(), "아 배고파", guessed=True)

    assert corrected.task == "search"
    assert corrected.categoryKeywords[0] == "맛집"


def test_a_guessed_intent_that_carried_a_prior_topic_still_leads_with_food() -> None:
    carried = QueryIntent(categoryKeywords=["박물관"], regionHints=["경주"])

    corrected = guard.apply_corrections(carried, "아 배고파", guessed=True)

    assert corrected.categoryKeywords[0] == "맛집"
    assert corrected.regionHints == ["경주"]


@pytest.mark.parametrize("word", ["호텔", "펜션", "모텔", "리조트", "게스트하우스", "숙소"])
def test_a_lodging_only_search_is_refused_because_we_do_not_serve_lodging(word: str) -> None:
    asked = QueryIntent(task="search", categoryKeywords=[word], regionHints=["제주"])

    corrected = guard.apply_corrections(asked, f"제주 {word} 추천해줘")

    assert corrected.task == "unsupported"
    assert corrected.categoryKeywords == []
    assert corrected.regionHints == []


def test_lodging_mentioned_beside_a_servable_type_keeps_the_search() -> None:
    asked = QueryIntent(task="search", categoryKeywords=["호텔", "카페"], regionHints=["제주"])

    corrected = guard.apply_corrections(asked, "제주 호텔 근처 카페")

    assert corrected.task == "search"
    assert corrected.categoryKeywords == ["호텔", "카페"]


def test_a_named_lodging_place_is_not_treated_as_a_lodging_category() -> None:
    asked = QueryIntent(task="search", categoryKeywords=["카페"], regionHints=["제주"])

    corrected = guard.apply_corrections(asked, "제주 신라호텔 근처 카페")

    assert corrected.task == "search"


def test_an_intent_needing_no_correction_is_returned_unchanged() -> None:
    asked = QueryIntent(task="search", categoryKeywords=["박물관"], regionHints=["경주"])

    assert guard.apply_corrections(asked, "경주 박물관") == asked
