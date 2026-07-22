from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

PlaceType = Literal["attraction", "restaurant", "cafe", "hotel", "region"]
ResolveStatus = Literal["matched", "ambiguous", "naver_only", "unmatched"]
SourceKind = Literal["text", "youtube", "image", "photo"]
TimeOfDay = Literal["morning", "afternoon", "evening"]


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


class ImportRequest(BaseModel):
    url: str | None = None
    text: str | None = None


class ImportResponse(BaseModel):
    sourceKind: SourceKind
    sourceTitle: str | None = None
    tripDays: int | None = None
    places: list[ResolvedPlace]


class AssembleRequest(BaseModel):
    places: list[ResolvedPlace] = Field(min_length=1)
    days: int | None = Field(None, ge=1, le=7)
    sourceKind: SourceKind = "text"
    sourceUrl: str | None = None
    sourceTitle: str | None = None


class ScheduleSlot(BaseModel):
    timeOfDay: TimeOfDay
    place: ResolvedPlace
    travelMinutesFromPrev: int | None = None


class ScheduleDay(BaseModel):
    day: int
    regionLabel: str | None = None
    slots: list[ScheduleSlot]


class PlanResponse(BaseModel):
    planId: str | None = None
    sourceTitle: str | None = None
    sourceUrl: str | None = None
    days: list[ScheduleDay]
    unplaced: list[ResolvedPlace] = Field(default_factory=list)


class PhotoMatchCard(BaseModel):
    contentId: str
    title: str
    category: str | None = None
    address: str | None = None
    lat: float | None = None
    lng: float | None = None
    imageUrl: str | None = None
    similarity: float


class PhotoMatchResponse(BaseModel):
    matches: list[PhotoMatchCard]


class FromSpotRequest(BaseModel):
    contentId: str
    days: int = Field(ge=1, le=7)


class AlternativesResponse(BaseModel):
    alternatives: list[ResolvedSpot]


class PlanEditRequest(BaseModel):
    op: Literal["remove", "replace"]
    day: int = Field(ge=1)
    slot: int = Field(ge=0)
    contentId: str | None = None
