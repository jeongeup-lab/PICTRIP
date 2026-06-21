"""CRS DTOs."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.core.kto_images import https_kto_image
from app.modules.spots.schemas import SpotCard

CourseType = Literal["efficient", "mood", "calm"]
DurationType = Literal["day", "1n2d", "2n3d", "3n_plus"]
PaceType = Literal["easy", "normal", "packed"]
CompanionType = Literal["solo", "couple", "friends", "family"]


class DraftRequest(BaseModel):
    baseContentId: str
    duration: DurationType
    pace: PaceType
    companion: CompanionType


class CourseItemCard(SpotCard):
    """A spot card inside a draft course — SPT SpotCard shape + position."""

    position: int


class DraftCourseOut(BaseModel):
    strategy: CourseType
    items: list[CourseItemCard]


class DraftResponse(BaseModel):
    baseContentId: str
    courses: list[DraftCourseOut]


# ---------- Saved courses (persistence, ADR-0011 sibling) ----------


class CourseItemIn(BaseModel):
    """One stop the client wants persisted in a saved course."""

    contentId: str
    position: int = Field(ge=0)


class CourseCreate(BaseModel):
    """Save a (usually drafted) course. `courseType` is the chosen draft
    strategy; duration/pace/companion carry the params that produced the draft
    so the saved metadata is consistent rather than fabricated."""

    name: str = Field(min_length=1, max_length=200)
    baseContentId: str | None = None
    durationType: DurationType
    paceType: PaceType
    companionType: CompanionType
    courseType: CourseType
    items: list[CourseItemIn] = Field(min_length=1)


class CourseSummary(BaseModel):
    id: int
    name: str
    courseType: CourseType
    durationType: DurationType
    itemCount: int
    coverImageUrl: str | None = None
    createdAt: datetime

    @field_validator("coverImageUrl")
    @classmethod
    def _upgrade_cover(cls, v: str | None) -> str | None:
        return https_kto_image(v)


class CourseDetail(CourseSummary):
    items: list[CourseItemCard]
