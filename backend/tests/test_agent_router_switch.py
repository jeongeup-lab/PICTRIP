from __future__ import annotations

from typing import Any

import pytest

from app.config import Settings
from app.modules.agent import search, toolloop
from app.modules.agent.routing import ToolCall
from app.modules.agent.schemas import AskAnchor, QueryIntent

pytestmark = pytest.mark.asyncio


def _tools(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(search, "settings", Settings(AGENT_ROUTER="tools"))


def _seen(monkeypatch: pytest.MonkeyPatch) -> dict[str, bool]:
    marks = {"tools": False, "branches": False}

    async def fake_route(*_args: Any, **_kwargs: Any) -> toolloop.Trace:
        marks["tools"] = True
        return toolloop.Trace(
            calls_made=[ToolCall(name="category_search", args={"regions": ["통영"]})]
        )

    async def fake_ask(*_args: Any, **_kwargs: Any) -> Any:
        marks["branches"] = True
        return "branches-response"

    monkeypatch.setattr(toolloop, "route", fake_route)
    monkeypatch.setattr(search.ask_service, "ask", fake_ask)
    return marks


async def _run(**overrides: Any) -> Any:
    payload: dict[str, Any] = {
        "question": "통영 카페",
        "lat": None,
        "lng": None,
        "image_bytes": None,
        "image_mime": None,
    }
    payload.update(overrides)
    return await search.run(None, None, None, **payload)


async def test_the_flag_defaults_to_the_existing_router() -> None:
    assert Settings().AGENT_ROUTER == "branches"


async def test_a_plain_question_goes_to_the_loop_when_the_flag_is_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _tools(monkeypatch)
    marks = _seen(monkeypatch)

    await _run()

    assert marks == {"tools": True, "branches": False}


async def test_the_flag_off_keeps_every_question_on_the_existing_router(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(search, "settings", Settings(AGENT_ROUTER="branches"))
    marks = _seen(monkeypatch)

    await _run()

    assert marks == {"tools": False, "branches": True}


@pytest.mark.parametrize(
    "unsupported",
    [
        {"image_bytes": b"jpeg"},
        {"intent": QueryIntent()},
        {"anchor": AskAnchor(action="nearby", contentId="1")},
        {"question": "   "},
        {"question": None},
    ],
)
async def test_paths_the_loop_cannot_handle_stay_on_the_existing_router(
    monkeypatch: pytest.MonkeyPatch, unsupported: dict[str, Any]
) -> None:
    """사진·앵커·칩 재생은 루프가 인자로 받지 못한다 — 넘기면 조용히 무시된다."""
    _tools(monkeypatch)
    marks = _seen(monkeypatch)

    await _run(**unsupported)

    assert marks == {"tools": False, "branches": True}


async def test_intent_is_rebuilt_from_the_last_search_the_model_made() -> None:
    """칩과 답변 문구가 의도를 읽는다 — 없으면 조건 표시가 통째로 빈다."""
    intent = toolloop.intent_of(
        [
            ToolCall(name="category_search", args={"regions": ["부산"], "categories": ["박물관"]}),
            ToolCall(
                name="category_search",
                args={"regions": ["통영"], "categories": ["카페"], "crowd": "quiet"},
            ),
        ]
    )

    assert intent.regionHints == ["통영"]
    assert intent.categoryKeywords == ["카페"]
    assert intent.crowdPreference == "quiet"


async def test_a_festival_call_marks_the_intent() -> None:
    intent = toolloop.intent_of([ToolCall(name="festival", args={"regions": ["부산"]})])

    assert intent.festivalOnly is True
    assert intent.regionHints == ["부산"]


async def test_unknown_mood_values_never_reach_the_intent() -> None:
    intent = toolloop.intent_of(
        [ToolCall(name="category_search", args={"moods": ["sea", "nonsense"]})]
    )

    assert intent.moodHints == ["sea"]


async def test_a_search_that_found_nothing_raises_the_contract_error() -> None:
    """검색을 했는데 빈손이면 AGENT_NO_RESULTS 다 — 도구를 안 부른 것과 다르다."""
    from app.modules.agent.errors import AgentNoResults

    searched = toolloop.Trace(calls_made=[ToolCall(name="category_search", args={})])

    with pytest.raises(AgentNoResults):
        toolloop.respond(searched, lat=None, lng=None)


async def test_an_empty_trace_with_conditions_offers_them_for_release() -> None:
    trace = toolloop.Trace(
        calls_made=[ToolCall(name="category_search", args={"regions": ["통영"], "indoor": True})]
    )

    response = toolloop.respond(trace, lat=None, lng=None)

    assert response.spots == []
    assert response.refinements


async def test_a_follow_up_with_context_stays_on_the_existing_router(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """루프는 context 를 인자로 못 받는다 — 넘기면 "그 주변" 이 전국을 뒤진다."""
    from app.modules.agent.schemas import AskContext, AskContextSpot

    _tools(monkeypatch)
    marks = _seen(monkeypatch)

    await _run(
        question="그 주변 카페",
        context=AskContext(spots=[AskContextSpot(contentId="1", title="감천문화마을")]),
    )

    assert marks == {"tools": False, "branches": True}


async def test_a_relaxing_retry_drops_the_condition_it_released() -> None:
    """누적하면 지운 조건이 살아남아 "수족관 조건으로" 라는 거짓 문구가 붙는다."""
    intent = toolloop.intent_of(
        [
            ToolCall(name="category_search", args={"regions": ["대전"], "categories": ["수족관"]}),
            ToolCall(name="category_search", args={"regions": ["대전"]}),
        ]
    )

    assert intent.categoryKeywords == []
    assert intent.regionHints == ["대전"]


async def test_a_turn_with_no_tool_call_is_smalltalk_not_a_search_failure() -> None:
    """기존 경로는 "안녕" 을 smalltalk 로 답한다 — AGENT_NO_RESULTS 가 되면 안 된다."""
    trace = toolloop.Trace(said="반가워요. 어디로 갈까요?")

    response = toolloop.respond(trace, lat=None, lng=None)

    assert response.spots == []
    assert "반가워요" in "".join(segment.text for segment in response.answer)


async def test_looked_up_facts_survive_into_the_answer() -> None:
    """상세 조회 값이 검색 문구로 덮이면 "몇 시에 열어?" 에 답을 못 한다."""
    trace = toolloop.Trace(
        calls_made=[ToolCall(name="spot_detail", args={"contentId": "1"})],
        facts=["경복궁 — 이용시간 09:00~18:00 · 쉬는 날 화요일"],
    )

    response = toolloop.respond(trace, lat=None, lng=None)

    assert "09:00~18:00" in "".join(segment.text for segment in response.answer)


async def test_facts_lead_the_answer_even_when_a_search_also_ran() -> None:
    """모델이 상세 조회 뒤 검색까지 하면 조회한 값이 검색 문구에 묻혔다."""
    trace = toolloop.Trace(
        calls_made=[
            ToolCall(name="spot_detail", args={"contentId": "1"}),
            ToolCall(name="category_search", args={"categories": ["고궁"]}),
        ],
        facts=["경복궁 — 이용시간 09:00~18:00"],
        rows=[_row("1", "경복궁")],
    )

    response = toolloop.respond(trace, lat=None, lng=None)

    text = "".join(segment.text for segment in response.answer)
    assert text.startswith("경복궁 — 이용시간 09:00~18:00")
    assert response.spots


def _row(content_id: str, title: str) -> Any:
    from app.modules.agent.repositories import CandidateRow

    return CandidateRow(
        content_id=content_id,
        title=title,
        addr1="서울특별시 종로구 1",
        region_name="서울특별시",
        sigungu_name="종로구",
        lat=37.5,
        lng=127.0,
        image_url="http://k/i.jpg",
        cpyrht_div_cd=None,
        concentration_rate=None,
    )
