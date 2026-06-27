"""SPT DTOs."""

from __future__ import annotations

from pydantic import BaseModel, field_validator

from app.core.kto_images import https_kto_image


class MoodOut(BaseModel):
    code: str
    name: str
    emoji: str
    sortOrder: int
    spotsCount: int = 0


class RegionOut(BaseModel):
    """A sido for the home region filter. code is the legal-dong sido code.
    "Nationwide" (전국) is client-side (omit the param) and not in this list."""

    code: str
    name: str


class SpotCard(BaseModel):
    contentId: str
    title: str
    firstImageUrl: str | None = None
    addr1: str | None = None
    mapx: float | None = None
    mapy: float | None = None
    # Subtype label = lcls_systm3_nm; legacy home routes put the coarse chip code here instead.
    category: str | None = None

    @field_validator("firstImageUrl")
    @classmethod
    def _upgrade_first_image(cls, v: str | None) -> str | None:
        return https_kto_image(v)


class SimilarNeighbor(SpotCard):
    distance: float


class SimilarQuery(SpotCard):
    """The spot the user picked. Same shape as SpotCard so the map can center on it."""


class SimilarResult(BaseModel):
    query: SimilarQuery
    neighbors: list[SimilarNeighbor]


class RelatedSpot(BaseModel):
    """KTO TarRlteTar entry (ADR-0005/0015). Name-keyed, no image, so it's a text
    chip; contentId is set only when the name matches an active spot (deep-link)."""

    name: str
    category: str | None = None
    regionName: str | None = None
    address: str | None = None
    rank: int | None = None
    contentId: str | None = None


class HomeHero(BaseModel):
    """Home-feed hero card. title keeps \\n verbatim (client renders pre-line)."""

    id: int
    slug: str
    title: str
    subtitle: str | None = None
    coverUrl: str | None = None

    @field_validator("coverUrl")
    @classmethod
    def _upgrade_cover(cls, v: str | None) -> str | None:
        return https_kto_image(v)


class HomeRail(BaseModel):
    """Home-feed mood rail: up to 8 SpotCards."""

    id: int
    title: str
    subtitle: str | None = None
    spots: list[SpotCard] = []


class HomeFeedResponse(BaseModel):
    heroes: list[HomeHero] = []
    rails: list[HomeRail] = []


class CurationDetailResponse(BaseModel):
    """Region/curation detail (S09 §5.2). subtitle is intentionally omitted —
    the detail screen shows title/lead/intro only."""

    id: int
    type: str
    slug: str
    title: str
    lead: str | None = None
    intro: str | None = None
    coverUrl: str | None = None
    spots: list[SpotCard] = []

    @field_validator("coverUrl")
    @classmethod
    def _upgrade_cover(cls, v: str | None) -> str | None:
        return https_kto_image(v)


class SpotImageOut(BaseModel):
    originImageUrl: str
    smallImageUrl: str | None = None

    @field_validator("originImageUrl", "smallImageUrl")
    @classmethod
    def _upgrade_image(cls, v: str | None) -> str | None:
        return https_kto_image(v)


class SpotIntro(BaseModel):
    """detailIntro2 display fields, verbatim from KTO. All optional."""

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
    category: str | None = None  # lcls_systm3_nm subtype label
    detailStatus: str
    images: list[SpotImageOut] = []
    intro: SpotIntro | None = None
