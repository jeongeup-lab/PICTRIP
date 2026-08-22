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
from app.modules.agent.emitter import Emitter, StepSignal
from app.modules.agent.repositories import CandidateRow
from app.modules.agent.routing import ToolCall, Turn
from app.modules.agent.schemas import (
    AnswerSegment,
    AskAnchor,
    AskContext,
    AskResponse,
    AskStep,
    DropAxis,
    Mood,
    QueryIntent,
    ToolName,
)
from app.modules.agent.services import answer as answer_service
from app.modules.agent.services import ask as ask_service
from app.modules.agent.services import retrieve
from app.modules.agent.services import suggest as suggest_service
from app.modules.agent.tools import CATALOG, ToolContext, schemas
from app.modules.agent.tools.itinerary import days_of

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
- 국내 여행지와 무관한 질문이면 도구를 부르지 않는다.
- "거기", "그 근처", "아까 그곳" 은 직전 결과를 가리킨다. 괄호 안 contentId 를
  그대로 도구 인자로 쓴다. 이름을 contentId 자리에 넣지 않는다."""

UNKNOWN_TOOL = "그런 도구는 없습니다."
TIMED_OUT = "도구가 시간 안에 끝나지 않았습니다. 조건을 좁혀 다시 부르세요."
TIMED_OUT_BADGE = "시간 초과"
REPEATED = "같은 도구를 같은 인자로 이미 불렀습니다. 조건을 바꾸세요."


@dataclass(slots=True)
class Trace:
    """루프가 무엇을 했는지. 섀도 대조가 읽는 값이다."""

    rows: list[CandidateRow] = field(default_factory=list)
    steps: list[AskStep] = field(default_factory=list)
    calls_made: list[ToolCall] = field(default_factory=list)
    facts: list[str] = field(default_factory=list)
    anchors: list[CandidateRow] = field(default_factory=list)
    emitter: Emitter | None = None

    def begin(self, label: str) -> None:
        """도구를 부르기 전에 알린다 — 끝나고 한꺼번에 내면 화면이 그동안 빈다."""
        if self.emitter is not None:
            self.emitter.send(
                StepSignal(index=len(self.steps), label=label, badge=None, status="run")
            )

    def finish(self, step: AskStep) -> None:
        self.steps.append(step)
        if self.emitter is not None:
            self.emitter.send(
                StepSignal(
                    index=len(self.steps) - 1, label=step.label, badge=step.badge, status="done"
                )
            )

    said: str = ask_service.BLANK_ANSWER
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
    label: str = tool.label(call.args)
    trace.begin(label)
    try:
        result = await asyncio.wait_for(tool.run(ctx, call.args), PER_TOOL_TIMEOUT_SECONDS)
    except TimeoutError:
        logger.warning("agent.router.tool_timeout", tool=call.name)
        trace.finish(AskStep(tool=tool.name, label=label, badge=TIMED_OUT_BADGE))
        return TIMED_OUT

    badge = "조회" if tool.carries_facts else f"{len(result.rows)}곳"
    trace.finish(AskStep(tool=tool.name, label=label, badge=badge))
    if tool.carries_facts:
        trace.facts.append(result.observation)
    elif result.fact:
        trace.facts.append(result.fact)
    seen_anchor = {row.content_id for row in trace.anchors}
    trace.anchors.extend(row for row in result.anchors if row.content_id not in seen_anchor)
    if not tool.carries_facts:
        seen = {row.content_id for row in trace.rows}
        trace.rows.extend(row for row in result.rows if row.content_id not in seen)
    return result.observation


CONTEXT_SPOTS = 8


ANCHOR_ASKS: dict[str, str] = {
    "food": "그 근처 맛집을 알려줘.",
    "cafe": "그 근처 카페를 알려줘.",
    "nearby": "그 근처 볼거리를 알려줘.",
    "related": "거기와 분위기가 닮은 곳을 알려줘.",
    "crowd": "거기 지금 붐비는지 알려줘.",
}

ANCHOR_CALLS: dict[str, tuple[ToolName, dict[str, Any]]] = {
    "food": ("nearby", {"kind": "food"}),
    "cafe": ("nearby", {"kind": "cafe"}),
    "nearby": ("nearby", {"kind": "nearby"}),
    "related": ("related", {}),
    "crowd": ("concentration", {}),
}


def anchor_question(anchor: AskAnchor) -> str:
    """탭에는 문장이 없다 — 없이 두면 모델이 원하지도 않은 도구를 더 부른다."""
    return ANCHOR_ASKS.get(anchor.action, "")


def anchor_call(anchor: AskAnchor) -> ToolCall | None:
    """카드 탭은 판단이 아니라 사실이다 — 모델에게 묻지 않고 코드가 도구로 옮긴다."""
    mapped = ANCHOR_CALLS.get(anchor.action)
    if mapped is None or anchor.contentId is None:
        return None
    name, extra = mapped
    return ToolCall(name=name, args={"contentId": anchor.contentId, **extra})


def call_from_intent(intent: QueryIntent) -> ToolCall:
    """intent_of 의 역방향. 칩은 조건을 하나 바꿔 같은 검색을 다시 돌리는 것이다."""
    if intent.festivalOnly:
        return ToolCall(name="festival", args={"regions": list(intent.regionHints)})
    args: dict[str, Any] = {}
    if intent.days is not None:
        args["days"] = intent.days
    if intent.regionHints:
        args["regions"] = list(intent.regionHints)
    if intent.categoryKeywords:
        args["categories"] = list(intent.categoryKeywords)
    if intent.moodHints:
        args["moods"] = list(intent.moodHints)
    if intent.crowdPreference != "any":
        args["crowd"] = intent.crowdPreference
    if intent.indoorOnly:
        args["indoor"] = True
    if intent.nearMe:
        args["near"] = True
    tool = "plan_itinerary" if intent.days is not None else "category_search"
    return ToolCall(name=tool, args=args)


def opening_turns(question: str, context: AskContext | None) -> list[Turn]:
    """직전 결과를 contentId 와 함께 준다 — 그래야 "그 근처" 가 도구 인자가 된다."""
    lines: list[str] = []
    if context is not None:
        if context.intent is not None:
            lines.append(f"직전 조건: {context.intent.model_dump_json(exclude_defaults=True)}")
        if context.spots:
            shown = " · ".join(
                f"{spot.title}({spot.contentId})" for spot in context.spots[:CONTEXT_SPOTS]
            )
            lines.append(f"직전 결과: {shown}")
        if context.focusContentId:
            lines.append(f"사용자가 보고 있는 카드: {context.focusContentId}")
    if not lines:
        return [Turn(role="user", text=question)]
    return [Turn(role="user", text="\n".join(lines) + f"\n\n이번 질문: {question}")]


async def route(
    ctx: ToolContext,
    question: str,
    *,
    context: AskContext | None = None,
    emitter: Emitter | None = None,
    opening: ToolCall | None = None,
) -> Trace:
    """모델이 도구를 고르고, 코드가 상한을 건다."""
    trace = Trace(emitter=emitter)
    started = monotonic()
    deadline = started + TOTAL_BUDGET_SECONDS
    turns: list[Turn] = opening_turns(question, context)
    fired: set[str] = set()
    if opening is not None:
        turns.append(Turn(role="call", calls=[opening]))
        observation = await _observe(ctx, opening, trace, fired)
        turns.append(Turn(role="observation", text=observation, tool_name=opening.name))
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
            if decision.text:
                trace.said = decision.text
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


_SEARCHES = frozenset(
    {"category_search", "title_search", "photo_match", "festival", "plan_itinerary"}
)


def intent_of(calls: list[ToolCall]) -> QueryIntent:
    """마지막으로 실제 검색한 호출만 읽는다.

    누적하면 완화 재시도가 지운 조건이 살아남아, 수족관을 지우고 다시 찾은 결과에
    "수족관 조건으로" 라는 문구와 칩이 붙는다.
    """
    searched = [call for call in calls if call.name in _SEARCHES]
    if not searched:
        return QueryIntent()
    last = searched[-1]
    args = last.args
    return QueryIntent(
        festivalOnly=last.name == "festival",
        regionHints=_texts(args, "regions"),
        categoryKeywords=_texts(args, "categories") or _texts(args, "keywords"),
        moodHints=[mood for mood in _texts(args, "moods") if mood in _MOODS],
        crowdPreference=(
            args["crowd"] if args.get("crowd") in ("quiet", "any", "popular") else "any"
        ),
        indoorOnly=bool(args.get("indoor")),
        nearMe=bool(args.get("near")),
        days=days_of(args) if last.name == "plan_itinerary" else None,
    )


_PLAN_AXES: frozenset[DropAxis] = frozenset({"crowd"})


def _axes(intent: QueryIntent) -> frozenset[DropAxis]:
    """일정은 지역이 필수라 지역·실내·거리 칩이 결과를 못 만든다."""
    return _PLAN_AXES if intent.days is not None else suggest_service.ALL_AXES


def _fact_segments(trace: Trace) -> list[AnswerSegment]:
    """조회한 값을 검색 문구 앞에 세운다 — 뒤에 붙이면 물어본 사실이 묻힌다."""
    if not trace.facts:
        return []
    return [AnswerSegment(text=" ".join(trace.facts) + " ")]


def _facts_response(trace: Trace, intent: QueryIntent) -> AskResponse:
    """조회한 값이 답이다. 기준 카드는 남긴다 — 없으면 다음 턴이 그 장소를 잃는다."""
    spots = [
        answer_service.card(row, intent=intent, lat=None, lng=None, near=False)
        for row in trace.anchors
    ]
    return AskResponse(
        steps=trace.steps,
        answer=_fact_segments(trace),
        spots=spots,
        totalCount=len(spots),
        intent=intent,
        facts=list(trace.facts),
        refinements=[],
    )


def _texts(args: Mapping[str, Any], key: str) -> list[str]:
    raw = args.get(key)
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, str) and item]


def respond(trace: Trace, *, lat: float | None, lng: float | None) -> AskResponse:
    """루프 결과를 기존 응답 조립에 넘긴다 — 작문과 칩은 손대지 않는다."""
    intent = intent_of(trace.calls_made)
    near = intent.nearMe and lat is not None and lng is not None
    if not trace.calls_made:
        return answer_service.talk_response(trace.steps, QueryIntent(task="smalltalk"), trace.said)
    if trace.facts and not trace.rows:
        return _facts_response(trace, intent)
    if not trace.rows:
        return answer_service.zero_response(
            trace.steps,
            intent,
            has_coords=lat is not None and lng is not None,
            region_hints=list(intent.regionHints),
            keywords=list(intent.categoryKeywords),
            axes=_axes(intent),
        )

    top = trace.rows[: retrieve.RESULT_LIMIT]
    spots = [answer_service.card(row, intent=intent, lat=lat, lng=lng, near=near) for row in top]
    spoken = answer_service.searched_intent(
        intent,
        has_coords=lat is not None and lng is not None,
        region_hints=list(intent.regionHints),
        keywords=list(intent.categoryKeywords),
    )
    searched = answer_service.answer_segments(top, intent=spoken, near=near, lat=lat, lng=lng)
    return AskResponse(
        steps=trace.steps,
        answer=[*_fact_segments(trace), *searched],
        spots=spots,
        totalCount=len(spots),
        intent=intent,
        facts=list(trace.facts),
        tagBasis=answer_service.tag_basis(top, spots, near=near),
        refinements=suggest_service.derive(
            intent,
            has_coords=lat is not None and lng is not None,
            result_count=len(spots),
            axes=_axes(intent),
            indoor_available=any(row.indoor for row in trace.rows),
        ),
    )
