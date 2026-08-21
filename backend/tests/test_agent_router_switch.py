from __future__ import annotations

from typing import Any

import pytest

from app.config import Settings
from app.modules.agent import search, toolloop
from app.modules.agent.routing import ToolCall
from app.modules.agent.schemas import AskAnchor, QueryIntent
from app.modules.agent.tools import ToolContext

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


async def test_a_follow_up_now_reaches_the_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.modules.agent.schemas import AskContext, AskContextSpot

    _tools(monkeypatch)
    marks = _seen(monkeypatch)

    await _run(
        question="그 주변 카페",
        context=AskContext(spots=[AskContextSpot(contentId="126198", title="감천문화마을")]),
    )

    assert marks == {"tools": True, "branches": False}


async def test_prior_results_carry_their_content_ids_into_the_prompt() -> None:
    """이름만 주면 모델이 contentId 자리에 이름을 넣는다 — 실제로 그랬다."""
    from app.modules.agent.schemas import AskContext, AskContextSpot

    turns = toolloop.opening_turns(
        "그 주변 카페",
        AskContext(spots=[AskContextSpot(contentId="126198", title="감천문화마을")]),
    )

    assert len(turns) == 1
    assert "감천문화마을(126198)" in turns[0].text
    assert "이번 질문: 그 주변 카페" in turns[0].text


async def test_the_focused_card_is_named_so_deixis_can_resolve() -> None:
    from app.modules.agent.schemas import AskContext

    turns = toolloop.opening_turns("여기 몇 시에 열어?", AskContext(focusContentId="126198"))

    assert "보고 있는 카드: 126198" in turns[0].text


async def test_a_first_turn_carries_no_context_preamble() -> None:
    turns = toolloop.opening_turns("통영 카페", None)

    assert [turn.text for turn in turns] == ["통영 카페"]


async def test_prior_spots_are_capped() -> None:
    from app.modules.agent.schemas import AskContext, AskContextSpot

    spots = [AskContextSpot(contentId=str(i), title=f"곳{i}") for i in range(8)]
    turns = toolloop.opening_turns("더 보여줘", AskContext(spots=spots))

    assert turns[0].text.count("(") == toolloop.CONTEXT_SPOTS


async def test_a_detail_answer_keeps_the_card_it_looked_up() -> None:
    """카드를 비우면 모바일 context 가 비고, 다음 "주차는?" 이 그 장소를 잃는다."""
    trace = toolloop.Trace(
        calls_made=[ToolCall(name="spot_detail", args={"contentId": "126508"})],
        facts=["경복궁 — 이용시간 09:00~18:00"],
        anchors=[_row("126508", "경복궁")],
    )

    response = toolloop.respond(trace, lat=None, lng=None)

    assert [spot.contentId for spot in response.spots] == ["126508"]
    assert "09:00~18:00" in "".join(segment.text for segment in response.answer)


async def test_a_looked_up_spot_is_not_counted_as_a_search_result() -> None:
    """상세 조회 대상이 검색 결과로 섞이면 "1곳을 찾았어요" 같은 거짓 문구가 붙는다."""
    from app.modules.agent.tools import CATALOG

    assert CATALOG["spot_detail"].carries_facts is True
    assert CATALOG["concentration"].carries_facts is True


@pytest.mark.parametrize(
    ("action", "tool", "extra"),
    [
        ("food", "nearby", {"kind": "food"}),
        ("cafe", "nearby", {"kind": "cafe"}),
        ("nearby", "nearby", {"kind": "nearby"}),
        ("related", "related", {}),
        ("crowd", "concentration", {}),
    ],
)
async def test_a_card_tap_becomes_a_tool_call(action: str, tool: str, extra: Any) -> None:
    """카드 탭은 판단이 아니라 사실이다 — 모델에게 물을 게 아니라 코드가 옮긴다."""
    call = toolloop.anchor_call(AskAnchor(action=action, contentId="126198"))

    assert call is not None
    assert call.name == tool
    assert call.args == {"contentId": "126198", **extra}


async def test_an_anchor_without_a_content_id_stays_on_the_existing_router(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """좌표만 있는 앵커는 도구로 못 옮긴다 — 넘기면 조용히 빈손이 된다."""
    _tools(monkeypatch)
    marks = _seen(monkeypatch)

    await _run(question="", anchor=AskAnchor(action="nearby"))

    assert marks == {"tools": False, "branches": True}


async def test_a_card_tap_reaches_the_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    _tools(monkeypatch)
    marks = _seen(monkeypatch)

    await _run(question="", anchor=AskAnchor(action="food", contentId="126198"))

    assert marks == {"tools": True, "branches": False}


async def test_the_opening_call_runs_before_the_model_decides(
    db_session: Any, redis_client_fake: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """앵커를 관찰로 먼저 넣어야 모델이 그 위에서 이어간다."""
    from app.modules.agent import toolloop as loop

    asked: list[int] = []

    class Counting:
        async def decide(self, **kwargs: Any) -> Any:
            asked.append(len(kwargs["turns"]))
            from app.modules.agent.routing import Decision

            return Decision(calls=[])

    monkeypatch.setattr(loop.llm, "get_routing_client", lambda: Counting())

    ctx = ToolContext(session=db_session, redis=redis_client_fake, kto=None)
    trace = await loop.route(ctx, "", opening=ToolCall(name="related", args={"contentId": "nope"}))

    assert trace.calls == 1
    assert asked and asked[0] >= 3


async def test_a_photo_reaches_the_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    _tools(monkeypatch)
    marks = _seen(monkeypatch)

    await _run(question="", image_bytes=b"jpeg-bytes", image_mime="image/jpeg")

    assert marks == {"tools": True, "branches": False}


async def test_a_photo_opens_with_the_upload_tool() -> None:
    """첨부는 사실이다 — 무슨 도구를 부를지 모델에게 물을 게 아니다."""
    call = search._opening(None, b"jpeg-bytes", None, None)

    assert call is not None
    assert call.name == "uploaded_photo"


async def test_an_anchor_wins_over_a_photo() -> None:
    """탭은 명시적 요청이라 첨부보다 앞선다."""
    call = search._opening(AskAnchor(action="food", contentId="1"), b"jpeg-bytes", None, None)

    assert call is not None
    assert call.name == "nearby"


async def test_the_photo_tool_says_when_nothing_was_attached(
    db_session: Any, redis_client_fake: Any
) -> None:
    """모델이 사진 없이 부르면 예외가 아니라 관찰로 되돌린다."""
    from app.modules.agent.tools import CATALOG

    ctx = ToolContext(session=db_session, redis=redis_client_fake, kto=None)
    result = await CATALOG["uploaded_photo"].run(ctx, {})

    assert result.rows == []
    assert "첨부하지 않았습니다" in result.observation


async def test_a_chip_replay_reaches_the_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    _tools(monkeypatch)
    marks = _seen(monkeypatch)

    await _run(question="", intent=QueryIntent(regionHints=["통영"]))

    assert marks == {"tools": True, "branches": False}


async def test_a_chip_carries_the_patched_condition() -> None:
    """칩은 조건 하나를 바꿔 같은 검색을 다시 도는 것이다."""
    from app.modules.agent.schemas import RefinePatch

    call = search._opening(
        None,
        None,
        QueryIntent(regionHints=["통영"], categoryKeywords=["카페"]),
        RefinePatch(crowdPreference="quiet"),
    )

    assert call is not None
    assert call.name == "category_search"
    assert call.args == {"regions": ["통영"], "categories": ["카페"], "crowd": "quiet"}


async def test_a_dropped_axis_leaves_the_call() -> None:
    """지역을 지운 칩이 지역을 그대로 실어 보내면 완화가 안 된다."""
    from app.modules.agent.schemas import RefinePatch

    call = search._opening(
        None,
        None,
        QueryIntent(regionHints=["통영"], categoryKeywords=["카페"]),
        RefinePatch(drop="region"),
    )

    assert call is not None
    assert "regions" not in call.args
    assert call.args["categories"] == ["카페"]


async def test_a_festival_intent_replays_on_the_festival_tool() -> None:
    call = search._opening(None, None, QueryIntent(festivalOnly=True, regionHints=["부산"]), None)

    assert call is not None
    assert call.name == "festival"


async def test_intent_round_trips_through_a_call() -> None:
    """intent_of 와 call_from_intent 가 서로의 역이 아니면 칩이 조건을 잃는다."""
    original = QueryIntent(
        regionHints=["통영"],
        categoryKeywords=["카페"],
        moodHints=["sea"],
        crowdPreference="quiet",
        indoorOnly=True,
    )

    restored = toolloop.intent_of([toolloop.call_from_intent(original)])

    assert restored.regionHints == original.regionHints
    assert restored.categoryKeywords == original.categoryKeywords
    assert restored.moodHints == original.moodHints
    assert restored.crowdPreference == original.crowdPreference
    assert restored.indoorOnly is True
