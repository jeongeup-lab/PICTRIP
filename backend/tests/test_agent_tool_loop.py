from __future__ import annotations

import asyncio
from typing import Any

import pytest

from app.modules.agent import toolloop as loop
from app.modules.agent.errors import AgentIntentUnavailable
from app.modules.agent.routing import Decision, ToolCall
from app.modules.agent.tools import ToolContext

pytestmark = pytest.mark.asyncio


class ScriptedRouter:
    """미리 정한 결정을 순서대로 돌려준다. 마지막 뒤로는 계속 멈춤이다."""

    def __init__(self, *decisions: Decision) -> None:
        self._decisions = list(decisions)
        self.asked = 0

    async def decide(self, **_kwargs: Any) -> Decision:
        self.asked += 1
        if not self._decisions:
            return Decision(calls=[])
        return self._decisions.pop(0)


@pytest.fixture
def ctx(db_session, redis_client_fake) -> ToolContext:
    return ToolContext(session=db_session, redis=redis_client_fake, kto=None)


def _wire(monkeypatch: pytest.MonkeyPatch, client: ScriptedRouter) -> None:
    monkeypatch.setattr(loop.llm, "get_routing_client", lambda: client)


def _call(**args: Any) -> ToolCall:
    return ToolCall(name="category_search", args=args)


async def test_no_tool_call_ends_the_turn_without_touching_tools(
    ctx: ToolContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = ScriptedRouter(Decision(calls=[]))
    _wire(monkeypatch, client)

    trace = await loop.route(ctx, "안녕")

    assert trace.calls == 0
    assert trace.rows == []
    assert trace.stopped == "done"


async def test_call_limit_stops_a_runaway_model(
    ctx: ToolContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    """상한이 없으면 모델이 도구를 무한히 불러 쿼터와 지연이 폭주한다."""
    forever = [Decision(calls=[_call(regions=[f"지역{i}"])]) for i in range(20)]
    _wire(monkeypatch, ScriptedRouter(*forever))

    trace = await loop.route(ctx, "아무거나")

    assert trace.calls == loop.MAX_TOOL_CALLS
    assert trace.stopped == "call_limit"


async def test_the_same_call_twice_is_refused_with_an_observation(
    ctx: ToolContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    same = _call(regions=["통영"])
    _wire(monkeypatch, ScriptedRouter(Decision(calls=[same]), Decision(calls=[same])))

    trace = await loop.route(ctx, "통영")

    assert trace.calls == 1
    assert len(trace.steps) == 1


async def test_argument_order_does_not_defeat_the_duplicate_guard() -> None:
    first = ToolCall(name="category_search", args={"regions": ["통영"], "indoor": True})
    second = ToolCall(name="category_search", args={"indoor": True, "regions": ["통영"]})

    assert loop.fingerprint(first) == loop.fingerprint(second)


async def test_calls_in_one_round_are_capped(
    ctx: ToolContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    """한 라운드에 8개를 부르면 예산이 한 번에 날아간다."""
    many = [_call(regions=[f"지역{i}"]) for i in range(8)]
    _wire(monkeypatch, ScriptedRouter(Decision(calls=many)))

    trace = await loop.route(ctx, "아무거나")

    assert trace.calls == loop.MAX_CALLS_PER_ROUND


async def test_an_unknown_tool_name_does_not_crash_the_loop(
    ctx: ToolContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    _wire(monkeypatch, ScriptedRouter(Decision(calls=[ToolCall(name="nope", args={})])))

    trace = await loop.route(ctx, "아무거나")

    assert trace.steps == []
    assert trace.stopped == "done"


async def test_a_hanging_tool_is_cut_off(ctx: ToolContext, monkeypatch: pytest.MonkeyPatch) -> None:
    async def never(*_args: Any, **_kwargs: Any) -> Any:
        await asyncio.sleep(30)

    monkeypatch.setattr(loop, "PER_TOOL_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setitem(
        loop.CATALOG, "category_search", _stub(loop.CATALOG["category_search"], never)
    )
    _wire(monkeypatch, ScriptedRouter(Decision(calls=[_call()])))

    trace = await loop.route(ctx, "아무거나")

    assert trace.calls == 1
    assert [step.badge for step in trace.steps] == [loop.TIMED_OUT_BADGE]


def _stub(tool: Any, run: Any) -> Any:
    from dataclasses import replace

    return replace(tool, run=run)


async def test_results_are_deduplicated_across_rounds(
    ctx: ToolContext, monkeypatch: pytest.MonkeyPatch, db_session
) -> None:
    from sqlalchemy import text

    await db_session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, addr1, first_image_url, "
            "show_flag, lcls_systm1, mapx, mapy) "
            "VALUES ('rt-1', 12, '한곳', '서울특별시 중구 1', 'http://k/i.jpg', 1, 'NA', 127.0, 37.0)"
        )
    )
    await db_session.flush()
    _wire(
        monkeypatch,
        ScriptedRouter(
            Decision(calls=[_call(regions=["서울"])]),
            Decision(calls=[_call(regions=["서울"], indoor=False)]),
        ),
    )

    trace = await loop.route(ctx, "아무거나")

    assert [row.content_id for row in trace.rows].count("rt-1") == 1


async def test_unrecoverable_tool_errors_stop_the_turn(
    ctx: ToolContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    """복구 가능한 빈손은 관찰로, 복구 불가는 그대로 올린다 — 모바일이 err.code 로 분기한다."""
    from app.modules.agent.errors import AgentFestivalUnavailable

    async def unavailable(*_args: Any, **_kwargs: Any) -> Any:
        raise AgentFestivalUnavailable()

    monkeypatch.setitem(loop.CATALOG, "festival", _stub(loop.CATALOG["festival"], unavailable))
    _wire(monkeypatch, ScriptedRouter(Decision(calls=[ToolCall(name="festival", args={})])))

    with pytest.raises(AgentFestivalUnavailable):
        await loop.route(ctx, "지금 열리는 축제")


async def test_steps_stream_while_the_loop_runs(
    ctx: ToolContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    """끝나고 한꺼번에 내면 사용자는 그동안 빈 화면을 본다 — 실측 7.9초."""
    from app.modules.agent.emitter import Emitter

    emitter = Emitter()
    _wire(monkeypatch, ScriptedRouter(Decision(calls=[_call(regions=[])])))

    trace = await loop.route(ctx, "아무거나", emitter=emitter)
    emitter.close()

    signals = [signal async for signal in emitter.drain()]
    assert [signal.status for signal in signals] == ["run", "done"]
    assert signals[0].badge is None
    assert signals[1].badge == f"{len(trace.rows)}곳"


async def test_a_loop_without_an_emitter_still_records_steps(
    ctx: ToolContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    _wire(monkeypatch, ScriptedRouter(Decision(calls=[_call(regions=[])])))

    trace = await loop.route(ctx, "아무거나")

    assert len(trace.steps) == 1


async def test_a_timed_out_tool_closes_its_step(
    ctx: ToolContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    """시작만 보내고 완료가 없으면 스피너가 영영 돈다."""
    from app.modules.agent.emitter import Emitter

    async def never(*_args: Any, **_kwargs: Any) -> Any:
        await asyncio.sleep(30)

    emitter = Emitter()
    monkeypatch.setattr(loop, "PER_TOOL_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setitem(
        loop.CATALOG, "category_search", _stub(loop.CATALOG["category_search"], never)
    )
    _wire(monkeypatch, ScriptedRouter(Decision(calls=[_call()])))

    await loop.route(ctx, "아무거나", emitter=emitter)
    emitter.close()

    signals = [signal async for signal in emitter.drain()]
    assert [signal.status for signal in signals] == ["run", "done"]
    assert signals[1].badge == loop.TIMED_OUT_BADGE


async def test_a_stopping_tool_ends_the_turn_before_the_next_call_in_the_round(
    ctx: ToolContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    """중단을 라운드 끝에서 보면 같은 라운드의 두 번째 호출이 이미 20곳을 낸 뒤다."""
    _wire(
        monkeypatch,
        ScriptedRouter(
            Decision(calls=[_call(), _call(regions=["서울"])]),
            Decision(calls=[]),
        ),
    )

    trace = await loop.route(ctx, "어디 갈까")

    assert trace.halt is True
    assert trace.stopped == "halted"
    assert trace.rows == []


async def test_a_dead_router_llm_still_answers(
    ctx: ToolContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    """라우터가 죽었다고 턴을 에러로 끝내면 '요청을 처리하지 못했어요' 가 뜬다."""

    class Dead:
        async def decide(self, **_kwargs: Any) -> Decision:
            raise AgentIntentUnavailable

    monkeypatch.setattr(loop.llm, "get_routing_client", lambda: Dead())

    trace = await loop.route(ctx, "가" * 480)

    assert trace.stopped == "llm_down"
    assert trace.rows == []
    response = loop.respond(trace, lat=None, lng=None)
    assert "어디로 갈지" in "".join(segment.text for segment in response.answer)


async def test_a_router_that_dies_midway_keeps_what_it_found(
    ctx: ToolContext, monkeypatch: pytest.MonkeyPatch, db_session
) -> None:
    """이미 찾은 결과를 버리면 도구를 부른 의미가 없다."""
    from sqlalchemy import text as sql

    await db_session.execute(
        sql(
            "INSERT INTO spots (content_id, content_type_id, title, addr1, first_image_url, "
            "show_flag, lcls_systm1, mapx, mapy) "
            "VALUES ('ld-1', 12, '한곳', '서울특별시 중구 1', 'http://k/i.jpg', 1, 'NA', 127.0, 37.0)"
        )
    )
    await db_session.flush()

    class DiesLater:
        def __init__(self) -> None:
            self.calls = 0

        async def decide(self, **_kwargs: Any) -> Decision:
            self.calls += 1
            if self.calls == 1:
                return Decision(calls=[_call(regions=["서울"])])
            raise AgentIntentUnavailable

    monkeypatch.setattr(loop.llm, "get_routing_client", lambda: DiesLater())

    trace = await loop.route(ctx, "서울 볼만한 곳")

    assert trace.stopped == "llm_down"
    assert [row.content_id for row in trace.rows] == ["ld-1"]
