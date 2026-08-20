from __future__ import annotations

import asyncio
from typing import Any

import pytest

from app.modules.agent import toolloop as loop
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

    assert trace.steps == []
    assert trace.calls == 1


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
            Decision(calls=[_call(regions=[])]),
            Decision(calls=[_call(indoor=False)]),
        ),
    )

    trace = await loop.route(ctx, "아무거나")

    assert [row.content_id for row in trace.rows].count("rt-1") == 1
