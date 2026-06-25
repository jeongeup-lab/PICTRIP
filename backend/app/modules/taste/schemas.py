"""TST DTOs."""

from __future__ import annotations

from pydantic import BaseModel

from app.modules.spots.schemas import SpotCard


class PhotoMatch(SpotCard):
    """SpotCard + CLIP similarity (1 - cosine distance) and optional location/region metadata."""

    similarity: float
    distance: float | None = None
    regionName: str | None = None
    sigunguName: str | None = None


class PhotoSearchResponse(BaseModel):
    matches: list[PhotoMatch] = []
    queryHadLocation: bool = False
