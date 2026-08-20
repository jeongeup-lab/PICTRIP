from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.kto.client import KtoClient
from app.modules.agent.errors import AgentNoResults
from app.modules.agent.repositories import CandidateRow
from app.modules.agent.schemas import ToolName

OBSERVATION_ROWS = 12
EMPTY = "결과 0곳. 조건을 줄이거나 지역을 넓혀 다시 부르세요."


@dataclass(frozen=True, slots=True)
class ToolContext:
    session: AsyncSession
    redis: Redis
    kto: KtoClient | None
    lat: float | None = None
    lng: float | None = None


@dataclass(frozen=True, slots=True)
class ToolResult:
    """rows 는 파이프라인이, observation 은 모델이 읽는다.

    후보 20곳을 통째로 모델에 돌려주면 토큰이 폭증하고 다음 호출 판단이 흐려진다.
    """

    rows: list[CandidateRow]
    observation: str


Run = Callable[["ToolContext", Mapping[str, Any]], Awaitable["ToolResult"]]


@dataclass(frozen=True, slots=True)
class Tool:
    name: ToolName
    description: str
    parameters: dict[str, Any]
    label: Callable[[Mapping[str, Any]], str]
    run: Run


def recoverable(run: Run) -> Run:
    """빈손을 예외가 아니라 관찰로 만든다 — 루프 안에서 예외는 턴을 죽인다."""

    async def guarded(ctx: ToolContext, args: Mapping[str, Any]) -> ToolResult:
        try:
            return await run(ctx, args)
        except AgentNoResults:
            return ToolResult(rows=[], observation=EMPTY)

    return guarded


def describe(rows: Sequence[CandidateRow], *, empty: str) -> str:
    if not rows:
        return empty
    shown = ", ".join(_one(row) for row in rows[:OBSERVATION_ROWS])
    if len(rows) > OBSERVATION_ROWS:
        return f"{len(rows)}곳: {shown} 외 {len(rows) - OBSERVATION_ROWS}곳"
    return f"{len(rows)}곳: {shown}"


def _one(row: CandidateRow) -> str:
    where = row.sigungu_name or row.region_name
    return f"{row.title}({where})" if where else row.title


def strings(args: Mapping[str, Any], key: str, *, limit: int) -> list[str]:
    raw = args.get(key)
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, str) and item][:limit]
