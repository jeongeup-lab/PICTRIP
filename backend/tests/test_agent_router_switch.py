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


async def test_intent_is_rebuilt_from_the_calls_the_model_made() -> None:
    """칩과 답변 문구가 의도를 읽는다 — 없으면 조건 표시가 통째로 빈다."""
    intent = toolloop.intent_of(
        [
            ToolCall(name="category_search", args={"regions": ["통영"], "categories": ["카페"]}),
            ToolCall(name="category_search", args={"crowd": "quiet", "indoor": True}),
        ]
    )

    assert intent.regionHints == ["통영"]
    assert intent.categoryKeywords == ["카페"]
    assert intent.crowdPreference == "quiet"
    assert intent.indoorOnly is True


async def test_a_festival_call_marks_the_intent() -> None:
    intent = toolloop.intent_of([ToolCall(name="festival", args={"regions": ["부산"]})])

    assert intent.festivalOnly is True
    assert intent.regionHints == ["부산"]


async def test_unknown_mood_values_never_reach_the_intent() -> None:
    intent = toolloop.intent_of(
        [ToolCall(name="category_search", args={"moods": ["sea", "nonsense"]})]
    )

    assert intent.moodHints == ["sea"]


async def test_an_empty_trace_with_no_conditions_raises_the_contract_error() -> None:
    """조건이 하나도 없으면 완화할 게 없다 — 모바일은 AGENT_NO_RESULTS 로 분기한다."""
    from app.modules.agent.errors import AgentNoResults

    with pytest.raises(AgentNoResults):
        toolloop.respond(toolloop.Trace(), lat=None, lng=None)


async def test_an_empty_trace_with_conditions_offers_them_for_release() -> None:
    trace = toolloop.Trace(
        calls_made=[ToolCall(name="category_search", args={"regions": ["통영"], "indoor": True})]
    )

    response = toolloop.respond(trace, lat=None, lng=None)

    assert response.spots == []
    assert response.refinements
