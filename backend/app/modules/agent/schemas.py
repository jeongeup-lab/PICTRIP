from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

PlaceType = Literal["attraction", "restaurant", "cafe", "hotel", "region"]
ResolveStatus = Literal["matched", "ambiguous", "naver_only", "unmatched"]
CrowdPreference = Literal["quiet", "any", "popular"]

ToolName = Literal[
    "intent",
    "photo_match",
    "resolve_place",
    "category_search",
    "title_search",
    "concentration",
    "nearby",
]


class ExtractedPlace(BaseModel):
    name: str
    nameKo: str | None = None
    placeType: PlaceType = "attraction"
    regionHint: str | None = None
    tip: str | None = None
    orderHint: int | None = None


class ResolvedSpot(BaseModel):
    source: Literal["kto", "naver"] = "kto"
    contentId: str | None = None
    title: str
    category: str | None = None
    address: str | None = None
    lat: float | None = None
    lng: float | None = None
    imageUrl: str | None = None


class ResolvedPlace(BaseModel):
    extracted: ExtractedPlace
    spot: ResolvedSpot | None = None
    confidence: float = 0.0
    status: ResolveStatus = "unmatched"


class QueryIntent(BaseModel):
    categoryKeywords: list[str] = Field(default_factory=list)
    regionHints: list[str] = Field(default_factory=list)
    namedPlaces: list[ExtractedPlace] = Field(default_factory=list)
    crowdPreference: CrowdPreference = "any"
    indoorOnly: bool = False
    nearMe: bool = False
    outOfScope: bool = False


class AskRequest(BaseModel):
    question: str | None = None
    lat: float | None = Field(None, ge=-90.0, le=90.0)
    lng: float | None = Field(None, ge=-180.0, le=180.0)


class AskStep(BaseModel):
    tool: ToolName
    label: str
    badge: str


class AnswerSegment(BaseModel):
    text: str
    emphasis: bool = False


class AgentSpotCard(BaseModel):
    contentId: str
    title: str
    regionLabel: str
    imageUrl: str | None = None
    tag: str | None = None
    lat: float | None = None
    lng: float | None = None


class AskResponse(BaseModel):
    steps: list[AskStep]
    answer: list[AnswerSegment]
    spots: list[AgentSpotCard]
    totalCount: int
    suggestions: list[str]
