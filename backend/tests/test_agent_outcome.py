from __future__ import annotations

import pytest

from app.modules.agent import outcome as outcome_service
from app.modules.agent.errors import AgentFestivalUnavailable, AgentOutOfScope
from app.modules.agent.schemas import AgentSpotCard, AnswerSegment, AskResponse, QueryIntent
from app.web.errors import ValidationFailed

BLANK = "어디로 갈지 한 줄만 알려주세요."


def _response(**kwargs: object) -> AskResponse:
    base: dict[str, object] = {
        "steps": [],
        "answer": [AnswerSegment(text="본문")],
        "spots": [],
        "totalCount": 0,
        "intent": QueryIntent(),
        "refinements": [],
    }
    base.update(kwargs)
    return AskResponse(**base)  # type: ignore[arg-type]


def card() -> AgentSpotCard:
    return AgentSpotCard(contentId="1", title="국립제주박물관", regionLabel="제주 제주시")


def test_results_win_over_every_other_reading_of_the_turn() -> None:
    outcome = outcome_service.classify(
        _response(spots=[card()], totalCount=1, intent=QueryIntent(task="smalltalk"))
    )

    assert isinstance(outcome, outcome_service.SpotResults)


def test_an_unsupported_request_is_its_own_outcome_not_an_empty_search() -> None:
    outcome = outcome_service.classify(_response(intent=QueryIntent(task="unsupported")))

    assert isinstance(outcome, outcome_service.OutOfCapability)


def test_a_greeting_is_its_own_outcome_not_an_empty_search() -> None:
    outcome = outcome_service.classify(_response(intent=QueryIntent(task="smalltalk")))

    assert isinstance(outcome, outcome_service.Smalltalk)


def test_a_question_with_no_axis_asks_for_more_rather_than_reporting_zero_results() -> None:
    outcome = outcome_service.classify(_response(intent=QueryIntent()))

    assert isinstance(outcome, outcome_service.NeedMoreInfo)


def test_a_searched_but_empty_turn_names_the_condition_that_blocked_it() -> None:
    outcome = outcome_service.classify(
        _response(intent=QueryIntent(regionHints=["울릉"], categoryKeywords=["미술관"]))
    )

    assert isinstance(outcome, outcome_service.NoResults)
    assert outcome.blocking_axis == "category"


def test_a_region_only_dead_end_blames_the_region_not_a_category_it_never_had() -> None:
    outcome = outcome_service.classify(_response(intent=QueryIntent(regionHints=["울릉"])))

    assert isinstance(outcome, outcome_service.NoResults)
    assert outcome.blocking_axis == "region"


def test_an_overseas_question_is_separated_from_a_genuine_failure() -> None:
    refusal = outcome_service.classify_error(AgentOutOfScope(), blank_answer=BLANK)

    assert isinstance(refusal, outcome_service.OutOfScope)


def test_an_upstream_outage_is_a_failure_and_keeps_its_error_code() -> None:
    refusal = outcome_service.classify_error(AgentFestivalUnavailable(), blank_answer=BLANK)

    assert isinstance(refusal, outcome_service.Failed)
    assert refusal.code == "AGENT_FESTIVAL_UNAVAILABLE"


def test_an_empty_request_is_guided_rather_than_shown_a_raw_validation_message() -> None:
    refusal = outcome_service.classify_error(ValidationFailed("empty"), blank_answer=BLANK)

    assert isinstance(refusal, outcome_service.Failed)
    assert refusal.message == BLANK


@pytest.mark.parametrize(
    ("outcome", "expected"),
    [
        (outcome_service.SpotResults(response=_response()), None),
        (outcome_service.Smalltalk(response=_response()), None),
        (outcome_service.OutOfCapability(response=_response()), "할 수 없는"),
        (outcome_service.NeedMoreInfo(response=_response()), "아직 검색하지 않았다"),
    ],
)
def test_the_writer_is_told_what_actually_happened_only_when_it_must_explain_itself(
    outcome: outcome_service.TurnOutcome, expected: str | None
) -> None:
    situation = outcome_service.situation_of(outcome)

    if expected is None:
        assert situation is None
    else:
        assert situation is not None and expected in situation


def test_the_writer_is_given_computed_facts_verbatim() -> None:
    """카드 순서만 보고 일차 구분과 이동 거리를 다시 추측하면 답이 어긋난다."""
    plan = "통영 2일 일정 — 1일차: 통영항 → 강구안 (이동 3km)"
    outcome = outcome_service.SpotResults(response=_response(facts=[plan]))

    situation = outcome_service.situation_of(outcome)

    assert situation is not None and plan in situation
