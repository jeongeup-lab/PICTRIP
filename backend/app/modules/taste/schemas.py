"""TST DTOs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DetectedMood(BaseModel):
    code: str
    confidence: float = Field(ge=0.0, le=1.0)


class PhotoSearchResult(BaseModel):
    sessionId: str
    detectedMoods: list[DetectedMood]
    topSpots: list[dict[str, Any]]
