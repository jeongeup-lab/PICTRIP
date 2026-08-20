"""라우팅 대화의 프로바이더 중립 표현.

Gemini 와 OpenAI 호환은 함수 호출 표현이 다르다. 루프가 두 문법을 알면 안 되므로
중립형을 두고 번역은 각 클라이언트가 맡는다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(frozen=True, slots=True)
class ToolCall:
    name: str
    args: dict[str, Any]


@dataclass(frozen=True, slots=True)
class Turn:
    role: Literal["user", "call", "observation"]
    text: str = ""
    calls: list[ToolCall] = field(default_factory=list)
    tool_name: str | None = None


@dataclass(frozen=True, slots=True)
class Decision:
    """도구를 더 부를지, 여기서 멈출지."""

    calls: list[ToolCall]
    text: str | None = None

    @property
    def done(self) -> bool:
        return not self.calls
