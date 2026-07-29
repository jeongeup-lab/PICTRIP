from __future__ import annotations

from typing import get_args

import pytest

from app.modules.agent.schemas import CrowdPreference, Mood, QueryIntent
from app.modules.agent.services import intent as intent_service
from scripts.eval_intent import GOLDEN_PATH, load_cases, score_case

CHIP_QUESTIONS = (
    "지금 열리는 축제",
    "사람 적은 바닷가",
    "비 와도 갈 만한 실내",
    "제주에서 한적한 곳",
    "여기서 가까운 곳",
)


def _explode(_: str) -> QueryIntent:
    raise AssertionError("preset must not reach the LLM")


def test_preset_table_covers_exactly_the_shipped_chip_questions() -> None:
    assert set(intent_service.PRESET_INTENTS) == set(CHIP_QUESTIONS)


@pytest.mark.parametrize("question", CHIP_QUESTIONS)
def test_every_chip_question_resolves_without_the_llm(question: str) -> None:
    assert intent_service.preset_intent(question) is not None


def test_preset_intents_carry_the_axes_the_chip_promises() -> None:
    assert intent_service.PRESET_INTENTS["지금 열리는 축제"].festivalOnly is True
    assert intent_service.PRESET_INTENTS["비 와도 갈 만한 실내"].indoorOnly is True
    assert intent_service.PRESET_INTENTS["여기서 가까운 곳"].nearMe is True

    sea = intent_service.PRESET_INTENTS["사람 적은 바닷가"]
    assert sea.moodHints == ["sea"]
    assert sea.crowdPreference == "quiet"

    jeju = intent_service.PRESET_INTENTS["제주에서 한적한 곳"]
    assert jeju.regionHints == ["제주"]
    assert jeju.crowdPreference == "quiet"


def test_preset_lookup_normalizes_surrounding_and_repeated_whitespace() -> None:
    assert (
        intent_service.preset_intent("  지금  열리는\t축제 ")
        == intent_service.PRESET_INTENTS["지금 열리는 축제"]
    )


def test_preset_lookup_misses_return_none_so_the_llm_still_runs() -> None:
    assert intent_service.preset_intent("여수 바다 보이는 카페") is None
    assert intent_service.preset_intent("지금 열리는 축제 알려줘") is None


def test_preset_result_is_a_copy_callers_cannot_mutate_the_table() -> None:
    first = intent_service.preset_intent("제주에서 한적한 곳")
    assert first is not None
    first.regionHints.append("부산")

    second = intent_service.preset_intent("제주에서 한적한 곳")
    assert second is not None
    assert second.regionHints == ["제주"]


async def test_resolve_intent_marks_preset_hits_with_the_rule_badge() -> None:
    resolved, source = await intent_service.resolve_intent("지금 열리는 축제")
    assert resolved.festivalOnly is True
    assert source == intent_service.PRESET_BADGE


async def test_resolve_intent_falls_through_to_the_llm_and_reports_the_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_extract(question: str) -> QueryIntent:
        return QueryIntent(regionHints=["여수"])

    monkeypatch.setattr(intent_service, "extract_intent", fake_extract)

    resolved, source = await intent_service.resolve_intent("여수 바다 보이는 카페")
    assert resolved.regionHints == ["여수"]
    assert source == "Gemini"


async def test_resolve_intent_never_calls_the_llm_for_a_chip_question(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(intent_service, "extract_intent", _explode)

    for question in CHIP_QUESTIONS:
        resolved, source = await intent_service.resolve_intent(question)
        assert source == intent_service.PRESET_BADGE
        assert resolved != QueryIntent()


GOLDEN_CASES = load_cases(GOLDEN_PATH, None)
SCORABLE_FIELDS = frozenset(QueryIntent.model_fields)


def test_golden_set_is_not_empty_and_ids_are_unique() -> None:
    assert len(GOLDEN_CASES) >= 40
    ids = [case.id for case in GOLDEN_CASES]
    assert len(set(ids)) == len(ids)


def test_golden_expectations_only_name_real_query_intent_fields() -> None:
    for case in GOLDEN_CASES:
        assert case.expect, f"{case.id} has no expectations"
        unknown = set(case.expect) - SCORABLE_FIELDS
        assert not unknown, f"{case.id} expects unknown field(s) {unknown}"


def test_golden_enum_expectations_stay_inside_the_schema_literals() -> None:
    moods = set(get_args(Mood))
    crowds = set(get_args(CrowdPreference))
    for case in GOLDEN_CASES:
        assert set(case.expect.get("moodHints", [])) <= moods, case.id
        if "crowdPreference" in case.expect:
            assert case.expect["crowdPreference"] in crowds, case.id


def test_golden_set_covers_every_routing_axis_and_both_scope_verdicts() -> None:
    def hits(field_name: str, value: object) -> int:
        return sum(1 for case in GOLDEN_CASES if case.expect.get(field_name) == value)

    assert hits("outOfScope", True) >= 5
    assert hits("outOfScope", False) >= 3
    assert hits("festivalOnly", True) >= 3
    assert hits("indoorOnly", True) >= 3
    assert hits("nearMe", True) >= 3
    assert hits("crowdPreference", "quiet") >= 3
    assert hits("crowdPreference", "popular") >= 2


def test_golden_set_exercises_every_mood_code() -> None:
    used = {mood for case in GOLDEN_CASES for mood in case.expect.get("moodHints", [])}
    assert used == set(get_args(Mood))


def test_every_chip_question_appears_in_the_golden_set() -> None:
    questions = {case.question for case in GOLDEN_CASES}
    assert set(CHIP_QUESTIONS) <= questions


def test_scorer_gives_a_perfect_score_to_an_exact_answer() -> None:
    case = next(c for c in GOLDEN_CASES if c.id == "combo-heavy")
    scores, misses = score_case(
        case,
        QueryIntent(
            regionHints=["여수"],
            crowdPreference="quiet",
            indoorOnly=True,
            categoryKeywords=["전시관"],
        ),
    )

    assert misses == {}
    assert set(scores.values()) == {1.0}


def test_scorer_treats_sido_suffix_variants_as_the_same_region() -> None:
    case = next(c for c in GOLDEN_CASES if c.id == "chip-jeju-quiet")
    scores, misses = score_case(case, QueryIntent(regionHints=["제주도"], crowdPreference="quiet"))

    assert scores["regionHints"] == 1.0
    assert misses == {}


def test_scorer_reports_a_partial_score_when_one_of_two_keywords_is_missing() -> None:
    case = next(c for c in GOLDEN_CASES if c.id == "category-only-3")
    scores, misses = score_case(case, QueryIntent(categoryKeywords=["박물관"]))

    assert 0.0 < scores["categoryKeywords"] < 1.0
    assert "categoryKeywords" in misses


def test_scorer_flags_a_wrong_scope_verdict_as_a_hard_miss() -> None:
    case = next(c for c in GOLDEN_CASES if c.id == "oos-paris")
    scores, misses = score_case(case, QueryIntent(outOfScope=False))

    assert scores["outOfScope"] == 0.0
    assert misses["outOfScope"] == (True, False)


def test_scorer_ignores_fields_the_case_does_not_pin() -> None:
    case = next(c for c in GOLDEN_CASES if c.id == "mood-sea")
    scores, _ = score_case(case, QueryIntent(moodHints=["sea"], regionHints=["부산"]))

    assert set(scores) == {"moodHints"}
