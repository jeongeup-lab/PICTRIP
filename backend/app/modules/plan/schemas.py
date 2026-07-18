from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

SlotType = Literal["attraction", "meal", "cafe"]
SlotSource = Literal["kto", "naver"]
ReplyType = Literal["text", "plan", "places", "clarify"]
TravelMode = Literal["walk", "transit"]


class TravelLeg(BaseModel):
    mode: TravelMode
    minutes: int


class ExternalLinks(BaseModel):
    naver: str | None = None
    kakao: str | None = None


class PlanSlot(BaseModel):
    type: SlotType
    source: SlotSource
    label: str
    name: str
    category: str | None = None
    contentId: str | None = None
    address: str | None = None
    lat: float | None = None
    lng: float | None = None
    imageUrl: str | None = None
    links: ExternalLinks = Field(default_factory=ExternalLinks)
    travelFromPrev: TravelLeg | None = None


class PlanDay(BaseModel):
    index: int
    slots: list[PlanSlot]


class PlanPayload(BaseModel):
    planId: str
    title: str
    summary: str
    region: str
    days: list[PlanDay]


class ChatRequest(BaseModel):
    threadId: str | None = Field(default=None, max_length=64)
    message: str = Field(min_length=1, max_length=500)


class PlaceCard(BaseModel):
    name: str
    category: str | None = None
    address: str | None = None
    lat: float | None = None
    lng: float | None = None
    links: ExternalLinks = Field(default_factory=ExternalLinks)


class ChatReply(BaseModel):
    type: ReplyType
    text: str
    chips: list[str] | None = None
    plan: PlanPayload | None = None
    places: list[PlaceCard] | None = None


class ChatResponse(BaseModel):
    threadId: str
    reply: ChatReply
