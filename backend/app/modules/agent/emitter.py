from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterable
from dataclasses import dataclass
from typing import Literal

from app.modules.agent.schemas import AskStep, ToolName

StepStatus = Literal["run", "done"]


@dataclass(frozen=True, slots=True)
class StepSignal:
    index: int
    label: str
    badge: str | None
    status: StepStatus


class Emitter:
    """검색이 진행되는 동안 스텝을 흘려보낸다.

    스텝은 작업이 끝난 뒤에야 배지와 함께 만들어진다 — 그것만 보내면 첫 스텝까지
    몇 초가 빈다. 시작 신호를 따로 내보내 그 공백을 없앤다.
    """

    def __init__(self) -> None:
        self._queue: asyncio.Queue[StepSignal | None] = asyncio.Queue()

    def send(self, signal: StepSignal) -> None:
        self._queue.put_nowait(signal)

    def close(self) -> None:
        self._queue.put_nowait(None)

    async def drain(self) -> AsyncIterator[StepSignal]:
        while True:
            signal = await self._queue.get()
            if signal is None:
                return
            yield signal


class Steps(list[AskStep]):
    """스텝 목록이면서 진행 상황을 내보낸다.

    list 를 상속해 append 호출부 스무 곳이 그대로 남는다.
    """

    def __init__(self, seed: Iterable[AskStep] = (), *, emitter: Emitter | None = None) -> None:
        super().__init__(seed)
        self.emitter = emitter

    def branch(self, seed: Iterable[AskStep] = ()) -> Steps:
        return Steps(seed, emitter=self.emitter)

    def begin(self, tool: ToolName, label: str) -> None:
        if self.emitter is not None:
            self.emitter.send(StepSignal(index=len(self), label=label, badge=None, status="run"))

    def append(self, step: AskStep) -> None:
        super().append(step)
        self._done(len(self) - 1, step)

    def __setitem__(self, index: int, step: AskStep) -> None:  # type: ignore[override]
        super().__setitem__(index, step)
        self._done(index, step)

    def _done(self, index: int, step: AskStep) -> None:
        if self.emitter is not None:
            self.emitter.send(
                StepSignal(index=index, label=step.label, badge=step.badge, status="done")
            )


def begin_step(steps: list[AskStep], tool: ToolName, label: str) -> None:
    """이어받은 목록이 Steps 일 때만 시작 신호를 낸다."""
    if isinstance(steps, Steps):
        steps.begin(tool, label)


def branch_of(steps: list[AskStep], seed: Iterable[AskStep] = ()) -> Steps:
    """이어받은 목록이 Steps 면 방출을 유지하고, 아니면 조용한 목록을 만든다."""
    if isinstance(steps, Steps):
        return steps.branch(seed)
    return Steps(seed)
