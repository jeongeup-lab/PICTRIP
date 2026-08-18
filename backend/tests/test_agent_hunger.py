from __future__ import annotations

import pytest

from app.modules.agent.schemas import QueryIntent
from app.modules.agent.services import guard


@pytest.mark.parametrize(
    "question",
    ["아 배고파", "배고프다", "출출한데", "허기지네", "뭐 먹지", "먹고 싶다", "배가 고픈데"],
)
def test_saying_i_am_hungry_is_a_request_for_food(question: str) -> None:
    assert guard.hungry(question) is True


@pytest.mark.parametrize(
    "question",
    ["너 밥 먹었어?", "당신은 뭐 먹어요", "너는 배고파?", "안녕", "경주 볼거리", "고마워"],
)
def test_asking_me_about_eating_stays_smalltalk(question: str) -> None:
    assert guard.hungry(question) is False


def test_a_hungry_turn_the_model_called_smalltalk_becomes_a_food_search() -> None:
    guessed = QueryIntent(task="smalltalk")

    fixed = guard._as_food_search(guessed)

    assert fixed.task == "search"
    assert fixed.categoryKeywords[0] == "맛집"


def test_the_correction_keeps_conditions_the_model_already_found() -> None:
    guessed = QueryIntent(task="smalltalk", regionHints=["경주"], nearMe=True)

    fixed = guard._as_food_search(guessed)

    assert fixed.regionHints == ["경주"]
    assert fixed.nearMe is True
