"""TST DTOs."""

from __future__ import annotations

from pydantic import BaseModel

from app.modules.spots.schemas import SpotCard


class PhotoMatch(SpotCard):
    """A photo-search match: a canonical SpotCard enriched with the CLIP
    similarity (1 - cosine distance) and optional location/region metadata.

    ``distance`` (metres from the query point) is present only when the request
    carried ``lat``/``lng``. ``regionName``/``sigunguName`` are filled when the
    spot has resolvable legal-dong codes; ``congestion`` is bucketed from
    spot_concentration when a row exists. All optional fields stay null/absent
    when their source is missing (omit-friendly).
    """

    similarity: float
    distance: float | None = None
    regionName: str | None = None
    sigunguName: str | None = None


class PhotoSearchResponse(BaseModel):
    matches: list[PhotoMatch] = []
    queryHadLocation: bool = False
