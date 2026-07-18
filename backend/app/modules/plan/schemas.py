from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

SlotType = Literal["attraction", "meal", "cafe"]
SlotSource = Literal["kto", "naver"]
ReplyType = Literal["text", "plan", "places", "pick", "spot", "clarify"]
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


class PickCandidate(BaseModel):
    contentId: str
    name: str
    category: str | None = None
    imageUrl: str


class PickPrompt(BaseModel):
    maxPicks: int
    spots: list[PickCandidate]


class UserLocation(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class ChatRequest(BaseModel):
    threadId: str | None = Field(default=None, max_length=64)
    message: str = Field(min_length=1, max_length=500)
    picks: list[str] | None = Field(default=None, max_length=6)
    selectId: str | None = Field(default=None, max_length=32)
    location: UserLocation | None = None


class PlaceCard(BaseModel):
    name: str
    source: Literal["naver", "kto"] = "naver"
    contentId: str | None = None
    category: str | None = None
    address: str | None = None
    lat: float | None = None
    lng: float | None = None
    imageUrl: str | None = None
    links: ExternalLinks = Field(default_factory=ExternalLinks)


class MatchCard(BaseModel):
    contentId: str
    name: str
    category: str | None = None
    address: str | None = None
    lat: float | None = None
    lng: float | None = None
    imageUrl: str | None = None
    similarity: float


class PhotoResponse(BaseModel):
    threadId: str
    description: str
    matches: list[MatchCard]


class ChatReply(BaseModel):
    type: ReplyType
    text: str
    chips: list[str] | None = None
    plan: PlanPayload | None = None
    places: list[PlaceCard] | None = None
    pick: PickPrompt | None = None
    spot: PlaceCard | None = None


class ChatResponse(BaseModel):
    threadId: str
    reply: ChatReply
