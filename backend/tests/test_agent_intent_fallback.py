from __future__ import annotations

from typing import Any

import pytest

from app.config import Settings
from app.modules.agent import llm
from app.modules.agent.errors import AgentIntentUnavailable
from app.modules.agent.schemas import AskContext, AskContextSpot, QueryIntent
from app.modules.agent.services import ask as ask_service
from app.modules.agent.services import intent as intent_service
from app.web.errors import RateLimited


class _FailingGemini:
    def __init__(self, error: Exception) -> None:
        self._error = error
        self.calls = 0

    async def generate_json(self, **kwargs: Any) -> Any:
        self.calls += 1
        raise self._error


class _StubGemini:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    async def generate_json(self, **kwargs: Any) -> Any:
        return self._payload


def test_fallback_reads_the_near_me_axis_from_the_question() -> None:
    assert intent_service.fallback_intent("근처에 갈 만한 데").nearMe is True
    assert intent_service.fallback_intent("여기서 가까운 계곡").nearMe is True
    assert intent_service.fallback_intent("제주 계곡").nearMe is False


def test_fallback_reads_the_crowd_axis_from_the_question() -> None:
    assert intent_service.fallback_intent("한적한 바다").crowdPreference == "quiet"
    assert intent_service.fallback_intent("사람 적은 곳").crowdPreference == "quiet"
    assert intent_service.fallback_intent("유명한 관광지").crowdPreference == "popular"
    assert intent_service.fallback_intent("제주 바다").crowdPreference == "any"


def test_fallback_reads_the_indoor_axis_from_the_question() -> None:
    assert intent_service.fallback_intent("비 오는 날 갈 만한 곳").indoorOnly is True
    assert intent_service.fallback_intent("실내에서 놀 데").indoorOnly is True
    assert intent_service.fallback_intent("더위 피할 곳").indoorOnly is True
    assert intent_service.fallback_intent("부산 계곡").indoorOnly is False


def test_fallback_picks_category_nouns_from_the_dictionary() -> None:
    guessed = intent_service.fallback_intent("부산 해수욕장 근처 맛집 알려줘")

    assert guessed.categoryKeywords == ["해수욕장", "맛집"]
    assert intent_service.fallback_intent("강릉 커피 마시고 싶어").categoryKeywords == ["카페"]
    assert intent_service.fallback_intent("놀이공원 가고 싶어").categoryKeywords == ["테마파크"]
    assert intent_service.fallback_intent("제주 바다").categoryKeywords == []


@pytest.fixture(autouse=True)
def _gemini_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    """이 파일은 Gemini 경로를 겨냥한다 — 기본 프로바이더(DeepSeek)에 기대지 않는다."""
    monkeypatch.setattr(llm, "settings", Settings(LLM_PROVIDER="gemini", GEMINI_API_KEY="k"))


@pytest.mark.parametrize(
    ("question", "code"),
    [
        ("바다 보이는 곳", "sea"),
        ("숲길 걷고 싶어", "mountain"),
        ("호수 있는 데", "lake"),
        ("섬에 가고 싶다", "island"),
        ("한옥 있는 곳", "hanok"),
        ("야경 예쁜 데", "night"),
        ("골목 구경", "street"),
    ],
)
def test_fallback_maps_mood_words_to_the_seven_codes(question: str, code: str) -> None:
    assert intent_service.fallback_intent(question).moodHints == [code]


def test_a_category_noun_wins_over_the_mood_word_inside_it() -> None:
    guessed = intent_service.fallback_intent("전통시장 구경하고 싶어")

    assert guessed.categoryKeywords == ["전통시장"]
    assert guessed.moodHints == []


def test_fallback_keeps_place_like_tokens_and_drops_question_words() -> None:
    assert intent_service.fallback_intent("제주에서 조용한 바다").regionHints == ["제주"]
    assert intent_service.fallback_intent("완도 가볼만한 곳").regionHints == ["완도"]
    assert intent_service.fallback_intent("강원도 계곡이랑 폭포 보고 싶어").regionHints == ["강원"]
    assert intent_service.fallback_intent("조용한 곳 추천해줘").regionHints == []


def test_a_greeting_is_smalltalk_with_every_axis_empty() -> None:
    guessed = intent_service.fallback_intent("고마워")

    assert guessed == QueryIntent(task="smalltalk")


def test_a_blank_question_keeps_the_default_intent() -> None:
    assert intent_service.fallback_intent("   ") == QueryIntent()


async def test_a_rate_limited_gemini_falls_back_instead_of_raising(monkeypatch) -> None:
    gemini = _FailingGemini(RateLimited())
    monkeypatch.setattr(llm, "get_client", lambda: gemini)

    outcome = await intent_service.resolve_intent("부산 계곡 한적한 곳")

    assert gemini.calls == 1
    assert outcome.fallback is True
    assert outcome.intent.categoryKeywords == ["계곡"]
    assert outcome.intent.regionHints == ["부산"]
    assert outcome.intent.crowdPreference == "quiet"


async def test_an_unavailable_gemini_falls_back_instead_of_raising(monkeypatch) -> None:
    monkeypatch.setattr(llm, "get_client", lambda: _FailingGemini(AgentIntentUnavailable()))

    outcome = await intent_service.resolve_intent("제주 바다")

    assert outcome.fallback is True
    assert outcome.intent.moodHints == ["sea"]


async def test_the_fallback_carries_the_prior_conditions_a_follow_up_leaves_out(
    monkeypatch,
) -> None:
    monkeypatch.setattr(llm, "get_client", lambda: _FailingGemini(RateLimited()))
    prior = QueryIntent(categoryKeywords=["계곡"], regionHints=["부산"])

    outcome = await intent_service.resolve_intent("더 한적한 곳", prior=prior)

    assert outcome.intent.regionHints == ["부산"]
    assert outcome.intent.categoryKeywords == ["계곡"]
    assert outcome.intent.crowdPreference == "quiet"


async def test_a_healthy_gemini_still_owns_the_intent(monkeypatch) -> None:
    monkeypatch.setattr(
        llm,
        "get_client",
        lambda: _StubGemini(
            {
                "task": "search",
                "categoryKeywords": ["박물관"],
                "regionHints": ["서울"],
                "crowdPreference": "any",
                "moodHints": [],
                "festivalOnly": False,
                "indoorOnly": True,
                "nearMe": False,
                "outOfScope": False,
            }
        ),
    )

    outcome = await intent_service.resolve_intent("서울 실내 박물관")

    assert outcome.fallback is False
    assert outcome.intent.categoryKeywords == ["박물관"]
    assert outcome.intent.indoorOnly is True


def test_demonstratives_do_not_become_region_hints() -> None:
    guessed = intent_service.fallback_intent("거기 근처 카페도 있어?")

    assert guessed.regionHints == []
    assert guessed.nearMe is True
    assert "카페" in guessed.categoryKeywords


def test_an_unresolvable_region_hint_does_not_veto_the_origin_anchor() -> None:
    context = AskContext(
        intent=QueryIntent(regionHints=["정읍"]),
        spots=[AskContextSpot(contentId="479904", title="정읍사공원")],
        focusContentId="479904",
    )
    guessed = QueryIntent(categoryKeywords=["카페"], regionHints=["거기"], nearMe=True)

    vetoed = ask_service._origin_anchor(guessed, context, region_named=True)
    kept = ask_service._origin_anchor(guessed, context, region_named=False)

    assert vetoed is None
    assert kept is not None
    assert kept.contentId == "479904"
    assert kept.action == "cafe"


def test_out_of_scope_requests_do_not_become_a_nationwide_search() -> None:
    assert intent_service.fallback_intent("주식 뭐 사면 돼?").task == "unsupported"
    assert intent_service.fallback_intent("숙소 예약해줄 수 있어?").task == "unsupported"
    assert intent_service.fallback_intent("부산 지하철 노선도 알려줘").task == "unsupported"
    assert intent_service.fallback_intent("파리 가볼 만한 곳 알려줘").outOfScope is True


def test_a_travel_question_with_a_bored_opener_still_searches() -> None:
    guessed = intent_service.fallback_intent("심심한데 부산 바다 보고 싶어")

    assert guessed.task == "search"
    assert guessed.moodHints == ["sea"]
    assert guessed.regionHints == ["부산"]
