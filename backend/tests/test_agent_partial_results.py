from __future__ import annotations

from app.modules.agent import outcome as outcome_service
from app.modules.agent.schemas import AgentSpotCard, AnswerSegment, AskResponse, QueryIntent
from app.modules.agent.services import food as food_service


def _response(**kw: object) -> AskResponse:
    base: dict[str, object] = {
        "steps": [],
        "answer": [AnswerSegment(text="ok")],
        "spots": [],
        "totalCount": 0,
        "intent": QueryIntent(),
        "refinements": [],
    }
    return AskResponse(**{**base, **kw})


def _card() -> AgentSpotCard:
    return AgentSpotCard(contentId="1", title="여수 밥집", regionLabel="전남 여수시")


def test_results_that_dropped_a_condition_are_partial_not_a_clean_hit() -> None:
    outcome = outcome_service.classify(
        _response(spots=[_card()], totalCount=1, unmet=["한적한 곳"])
    )

    assert isinstance(outcome, outcome_service.PartialResults)
    assert outcome.unmet == ["한적한 곳"]


def test_results_with_every_condition_applied_stay_a_clean_hit() -> None:
    outcome = outcome_service.classify(_response(spots=[_card()], totalCount=1))

    assert isinstance(outcome, outcome_service.SpotResults)


def test_the_writer_is_told_what_it_could_not_honour() -> None:
    outcome = outcome_service.classify(_response(spots=[_card()], totalCount=1, unmet=["실내"]))

    assert outcome_service.situation_of(outcome) is not None
    assert "실내" in (outcome_service.situation_of(outcome) or "")


def test_an_empty_result_is_never_partial_because_nothing_was_delivered() -> None:
    outcome = outcome_service.classify(
        _response(intent=QueryIntent(regionHints=["여수"]), unmet=["실내"])
    )

    assert not isinstance(outcome, outcome_service.PartialResults)


def test_dropped_food_filters_are_named_in_the_users_own_terms() -> None:
    assert food_service.dropped_labels(
        QueryIntent(crowdPreference="quiet", indoorOnly=True, moodHints=["sea"])
    ) == ["한적한 곳", "실내", "분위기"]


def test_nothing_is_named_when_no_filter_was_dropped() -> None:
    assert food_service.dropped_labels(QueryIntent()) == []
