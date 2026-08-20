"""도구를 고르는 루프.

services/ 가 아니라 그 바깥에 둔다 — tools/ 가 services/ 를 부르므로 여기서
services/ 안에 들어가면 패키지 순환이 된다. 방향은 router → tools → services 다.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from time import monotonic
from typing import Any, get_args

from app.core.logging import get_logger
from app.modules.agent import llm
from app.modules.agent.repositories import CandidateRow
from app.modules.agent.routing import ToolCall, Turn
from app.modules.agent.schemas import AskResponse, AskStep, Mood, QueryIntent
from app.modules.agent.services import answer as answer_service
from app.modules.agent.services import retrieve
from app.modules.agent.services import suggest as suggest_service
from app.modules.agent.tools import CATALOG, ToolContext, schemas

logger = get_logger(__name__)

_MOODS = frozenset(get_args(Mood))

MAX_TOOL_CALLS = 4
MAX_CALLS_PER_ROUND = 3
TOTAL_BUDGET_SECONDS = 12.0
PER_TOOL_TIMEOUT_SECONDS = 4.0

SYSTEM = """너는 국내 여행지 검색 라우터다. 질문에 답하려면 어떤 도구를 어떤 인자로
불러야 하는지만 정한다. 답변 문장은 쓰지 않는다.

- 결과가 0곳이면 관찰을 읽고 조건을 바꿔 다시 부른다. 같은 인자로 다시 부르지 않는다.
- 필요한 만큼만 부른다. 충분하면 도구를 부르지 말고 끝낸다.
- 국내 여행지와 무관한 질문이면 도구를 부르지 않는다."""

UNKNOWN_TOOL = "그런 도구는 없습니다."
TIMED_OUT = "도구가 시간 안에 끝나지 않았습니다. 조건을 좁혀 다시 부르세요."
REPEATED = "같은 도구를 같은 인자로 이미 불렀습니다. 조건을 바꾸세요."


@dataclass(slots=True)
class Trace:
    """루프가 무엇을 했는지. 섀도 대조가 읽는 값이다."""

    rows: list[CandidateRow] = field(default_factory=list)
    steps: list[AskStep] = field(default_factory=list)
    calls_made: list[ToolCall] = field(default_factory=list)
    calls: int = 0
    rounds: int = 0
    stopped: str = "done"
    elapsed: float = 0.0


def fingerprint(call: ToolCall) -> str:
    payload = json.dumps(call.args, sort_keys=True, ensure_ascii=False)
    return f"{call.name}:{hashlib.sha1(payload.encode()).hexdigest()[:12]}"


async def _run_one(ctx: ToolContext, call: ToolCall, trace: Trace) -> str:
    tool = next((known for name, known in CATALOG.items() if name == call.name), None)
    if tool is None:
        return UNKNOWN_TOOL
    try:
        result = await asyncio.wait_for(tool.run(ctx, call.args), PER_TOOL_TIMEOUT_SECONDS)
    except TimeoutError:
        logger.warning("agent.router.tool_timeout", tool=call.name)
        return TIMED_OUT

    label: str = tool.label(call.args)
    trace.steps.append(AskStep(tool=tool.name, label=label, badge=f"{len(result.rows)}곳"))
    seen = {row.content_id for row in trace.rows}
    trace.rows.extend(row for row in result.rows if row.content_id not in seen)
    return result.observation


async def route(ctx: ToolContext, question: str) -> Trace:
    """모델이 도구를 고르고, 코드가 상한을 건다."""
    trace = Trace()
    started = monotonic()
    deadline = started + TOTAL_BUDGET_SECONDS
    turns: list[Turn] = [Turn(role="user", text=question)]
    fired: set[str] = set()
    client = llm.get_routing_client()
    declared = schemas()

    while True:
        if trace.calls >= MAX_TOOL_CALLS:
            trace.stopped = "call_limit"
            break
        if monotonic() >= deadline:
            trace.stopped = "budget"
            break

        decision = await client.decide(system=SYSTEM, turns=turns, tools=declared)
        if decision.done:
            break

        picked = decision.calls[:MAX_CALLS_PER_ROUND]
        turns.append(Turn(role="call", calls=picked))
        trace.rounds += 1

        for call in picked:
            observation = await _observe(ctx, call, trace, fired)
            turns.append(Turn(role="observation", text=observation, tool_name=call.name))

    trace.elapsed = monotonic() - started
    logger.info(
        "agent.router.done",
        calls=trace.calls,
        rounds=trace.rounds,
        results=len(trace.rows),
        stopped=trace.stopped,
        elapsed_ms=round(trace.elapsed * 1000),
    )
    return trace


async def _observe(ctx: ToolContext, call: ToolCall, trace: Trace, fired: set[str]) -> str:
    """도구는 한 세션을 공유하므로 순차로만 돈다 — asyncpg 는 동시 사용을 거부한다."""
    if trace.calls >= MAX_TOOL_CALLS:
        return REPEATED
    mark = fingerprint(call)
    if mark in fired:
        return REPEATED
    fired.add(mark)
    trace.calls += 1
    trace.calls_made.append(call)
    return await _run_one(ctx, call, trace)


def intent_of(calls: list[ToolCall]) -> QueryIntent:
    """도구 인자가 곧 의도다 — 문구를 짓고 칩을 뽑는 데 다시 LLM 을 부르지 않는다."""
    merged: dict[str, Any] = {}
    for call in calls:
        args = call.args
        if call.name == "festival":
            merged["festivalOnly"] = True
        if regions := _texts(args, "regions"):
            merged["regionHints"] = regions
        keywords = _texts(args, "categories") or _texts(args, "keywords")
        if keywords:
            merged["categoryKeywords"] = keywords
        if moods := [mood for mood in _texts(args, "moods") if mood in _MOODS]:
            merged["moodHints"] = moods
        if args.get("crowd") in ("quiet", "any", "popular"):
            merged["crowdPreference"] = args["crowd"]
        if args.get("indoor"):
            merged["indoorOnly"] = True
        if args.get("near"):
            merged["nearMe"] = True
    return QueryIntent(**merged)


def _texts(args: Mapping[str, Any], key: str) -> list[str]:
    raw = args.get(key)
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, str) and item]


def respond(trace: Trace, *, lat: float | None, lng: float | None) -> AskResponse:
    """루프 결과를 기존 응답 조립에 넘긴다 — 작문과 칩은 손대지 않는다."""
    intent = intent_of(trace.calls_made)
    near = intent.nearMe and lat is not None and lng is not None
    if not trace.rows:
        return answer_service.zero_response(
            trace.steps,
            intent,
            has_coords=lat is not None and lng is not None,
            region_hints=list(intent.regionHints),
            keywords=list(intent.categoryKeywords),
            axes=suggest_service.ALL_AXES,
        )

    top = trace.rows[: retrieve.RESULT_LIMIT]
    spots = [answer_service.card(row, intent=intent, lat=lat, lng=lng, near=near) for row in top]
    spoken = answer_service.searched_intent(
        intent,
        has_coords=lat is not None and lng is not None,
        region_hints=list(intent.regionHints),
        keywords=list(intent.categoryKeywords),
    )
    return AskResponse(
        steps=trace.steps,
        answer=answer_service.answer_segments(top, intent=spoken, near=near, lat=lat, lng=lng),
        spots=spots,
        totalCount=len(spots),
        intent=intent,
        tagBasis=answer_service.tag_basis(top, spots, near=near),
        refinements=suggest_service.derive(
            intent,
            has_coords=lat is not None and lng is not None,
            result_count=len(spots),
            axes=suggest_service.ALL_AXES,
            indoor_available=any(row.indoor for row in trace.rows),
        ),
    )
