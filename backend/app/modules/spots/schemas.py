"""SPT DTOs."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, field_validator

from app.core.kto_images import https_kto_image


class MoodOut(BaseModel):
    code: str
    name: str
    emoji: str
    sortOrder: int
    spotsCount: int = 0


class RegionOut(BaseModel):
    """A sido (top-level province) for the home region filter. `code` is the
    legal-dong sido code (e.g. "51"), the value `/moods/{code}/spots?region=`
    expects. "Nationwide" (전국) is a client-side concept (omit the param), so it
    is not in this list.
    """

    code: str
    name: str


class SpotCard(BaseModel):
    contentId: str
    title: str
    firstImageUrl: str | None = None
    addr1: str | None = None
    mapx: float | None = None
    mapy: float | None = None
    # Canonical subtype label = lcls_systm_codes.lcls_systm3_nm (e.g. "사적지",
    # "찻집"). Endpoints map it from SpotCardRow.lcls_systm3_nm. Legacy home
    # routes (by-region/batch) still populate it with the coarse chip code
    # instead; all other consumers serialize null (backward compat —
    # SimilarNeighbor/SimilarQuery inherit it as null too).
    category: str | None = None
    # Optional crowd-level bucket from spot_concentration (Task 9). Defaults None
    # and is omit-friendly — endpoints enrich it via load_congestion() only where
    # the screen shows it; everywhere else it stays null.
    congestion: Literal["low", "medium", "high"] | None = None

    @field_validator("firstImageUrl")
    @classmethod
    def _upgrade_first_image(cls, v: str | None) -> str | None:
        return https_kto_image(v)


class SimilarNeighbor(SpotCard):
    distance: float


class SimilarQuery(SpotCard):
    """The spot the user picked. Same shape as SpotCard (incl. addr1/mapx/mapy)
    so the map can center on and mark the query spot instead of guessing from
    the first neighbor's coords."""


class SimilarResult(BaseModel):
    query: SimilarQuery
    neighbors: list[SimilarNeighbor]


class RelatedSpot(BaseModel):
    """A "places people search together" entry from KTO TarRlteTar
    (ADR-0005/0015). TarRlteTar is
    name-keyed and carries no image (verified against the official field spec),
    so this is a text chip, not an image card. `contentId` is filled only when
    the related name exactly matches one of our active spots, letting that chip
    deep-link to /spots/{contentId}; otherwise it stays a plain chip."""

    name: str
    category: str | None = None
    regionName: str | None = None
    address: str | None = None
    rank: int | None = None
    contentId: str | None = None


class TrendingSpot(BaseModel):
    """A 전국 "집중률 TOP" entry (#2 home, ADR-0016). `concentrationRate` is KTO's
    published 관광지 집중률 (0-100, relative to the spot's own peak), `rank` is
    1-based over the returned slice."""

    contentId: str
    title: str
    firstImageUrl: str | None = None
    addr1: str | None = None
    regionName: str | None = None
    mapx: float | None = None
    mapy: float | None = None
    concentrationRate: float
    rank: int

    @field_validator("firstImageUrl")
    @classmethod
    def _upgrade_first_image(cls, v: str | None) -> str | None:
        return https_kto_image(v)


class MoodTag(BaseModel):
    code: str
    name: str
    emoji: str


class SpotImageOut(BaseModel):
    originImageUrl: str
    smallImageUrl: str | None = None

    @field_validator("originImageUrl", "smallImageUrl")
    @classmethod
    def _upgrade_image(cls, v: str | None) -> str | None:
        return https_kto_image(v)


class SpotIntro(BaseModel):
    """detailIntro2 display fields. All optional — null fields are hidden by the
    client. Sourced verbatim from KTO (no modification)."""

    usetime: str | None = None
    restdate: str | None = None
    parking: str | None = None
    infocenter: str | None = None
    firstmenu: str | None = None
    treatmenu: str | None = None


class SpotDetailResponse(SpotCard):
    addr2: str | None = None
    overview: str | None = None
    homepage: str | None = None
    tel: str | None = None
    regionName: str | None = None
    sigunguName: str | None = None
    category: str | None = None  # lcls_systm3_nm 세분 라벨
    detailStatus: str
    moods: list[MoodTag] = []
    images: list[SpotImageOut] = []
    intro: SpotIntro | None = None
