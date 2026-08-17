from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.modules.agent.schemas import AskResponse, DropAxis
from app.web.errors import AppError, ValidationFailed

BlockingAxis = DropAxis | Literal["unknown"]


@dataclass(frozen=True, slots=True)
class SpotResults:
    response: AskResponse


@dataclass(frozen=True, slots=True)
class NoResults:
    response: AskResponse
    blocking_axis: BlockingAxis


@dataclass(frozen=True, slots=True)
class NeedMoreInfo:
    response: AskResponse


@dataclass(frozen=True, slots=True)
class OutOfCapability:
    response: AskResponse


@dataclass(frozen=True, slots=True)
class Smalltalk:
    response: AskResponse


@dataclass(frozen=True, slots=True)
class OutOfScope:
    message: str


@dataclass(frozen=True, slots=True)
class Failed:
    code: str
    message: str


TurnOutcome = (
    SpotResults | NoResults | NeedMoreInfo | OutOfCapability | Smalltalk | OutOfScope | Failed
)

PROSE_SITUATIONS: dict[type, str] = {
    NoResults: "검색은 했지만 조건에 맞는 곳이 하나도 없었다",
    NeedMoreInfo: "검색할 조건이 없어 아직 검색하지 않았다",
    OutOfCapability: "이 앱이 할 수 없는 요구라 검색하지 않았다",
}


def _blocking_axis(response: AskResponse) -> BlockingAxis:
    intent = response.intent
    if intent.categoryKeywords:
        return "category"
    if intent.indoorOnly:
        return "indoor"
    if intent.crowdPreference != "any":
        return "crowd"
    if intent.nearMe:
        return "near"
    if intent.regionHints:
        return "region"
    return "unknown"


def _has_axis(response: AskResponse) -> bool:
    intent = response.intent
    return bool(
        intent.categoryKeywords
        or intent.regionHints
        or intent.namedPlaces
        or intent.moodHints
        or intent.festivalOnly
        or intent.indoorOnly
        or intent.nearMe
    )


def classify(response: AskResponse) -> TurnOutcome:
    if response.spots:
        return SpotResults(response=response)
    if response.intent.task == "unsupported":
        return OutOfCapability(response=response)
    if response.intent.task == "smalltalk":
        return Smalltalk(response=response)
    if not _has_axis(response):
        return NeedMoreInfo(response=response)
    return NoResults(response=response, blocking_axis=_blocking_axis(response))


def classify_error(exc: AppError, *, blank_answer: str) -> OutOfScope | Failed:
    if exc.code == "AGENT_OUT_OF_SCOPE":
        return OutOfScope(message=exc.message)
    message = blank_answer if isinstance(exc, ValidationFailed) else exc.message
    return Failed(code=exc.code, message=message)


def situation_of(outcome: TurnOutcome) -> str | None:
    return PROSE_SITUATIONS.get(type(outcome))
