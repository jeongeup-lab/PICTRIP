"""CRS service row DTOs shared by draft generation and saved-course storage."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class CourseItemCard:
    """A spot card inside a course, carrying its 0-based itinerary position."""

    position: int
    content_id: str
    title: str
    first_image_url: str | None
    addr1: str | None
    mapx: float | None
    mapy: float | None


@dataclass(frozen=True)
class CourseSummaryRow:
    id: int
    name: str
    course_type: str
    duration_type: str
    item_count: int
    cover_image_url: str | None
    created_at: datetime


@dataclass(frozen=True)
class CourseDetailRow:
    summary: CourseSummaryRow
    items: list[CourseItemCard]
