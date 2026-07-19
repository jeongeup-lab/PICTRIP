"""CHT DTOs. Mobile-facing camelCase, JSend-wrapped by routes."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, model_validator


class ChatCondition(BaseModel):
    id: str
    label: str
    exclude: bool = False


class ChatCard(BaseModel):
    contentId: str
    title: str
    firstImageUrl: str
    category: str | None
    regionLabel: str
    why: str
    quiet: bool | None


class ChatAnswer(BaseModel):
    id: str
    label: str
    # ask: send label's utterance · skip: advance axis · remove: drop a condition ·
    # commit/restart: client-local (build conclusion / reset).
    kind: Literal["ask", "skip", "remove", "commit", "restart"]
    utterance: str | None = None
    removeConditionId: str | None = None


class ChatTurnRequest(BaseModel):
    sessionId: str | None = None
    utterance: str | None = None
    removeConditionId: str | None = None
    skip: bool = False

    @model_validator(mode="after")
    def _require_action(self) -> ChatTurnRequest:
        if not self.utterance and not self.removeConditionId and not self.skip:
            raise ValueError("utterance, removeConditionId, or skip required")
        return self


class ChatTurnResponse(BaseModel):
    sessionId: str
    round: int
    phase: Literal["refining", "converged", "empty"]
    poolTotal: int
    candidateCount: int
    conditions: list[ChatCondition]
    botText: str
    cards: list[ChatCard]
    question: str
    answers: list[ChatAnswer]


class ChatMoodCoversRequest(BaseModel):
    utterances: list[str]


class ChatMoodCover(BaseModel):
    utterance: str
    coverUrl: str | None


class ChatMoodCoversResponse(BaseModel):
    covers: list[ChatMoodCover]
