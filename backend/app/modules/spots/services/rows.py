"""SPT service row dataclasses (DTOs returned by the service layer)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SpotCardRow:
    content_id: str
    title: str
    first_image_url: str | None
    addr1: str | None
    mapx: float | None
    mapy: float | None
    category: str | None = None  # derive_category chip code, NOT lcls_systm3_nm
    # KTO subtype label (lcls_systm_codes.lcls_systm3_nm, e.g. "사적지", "찻집").
    # The canonical card's `category` is sourced from this (Task 9); the coarse
    # `category` chip code above is the legacy nearby/home value.
    lcls_systm3_nm: str | None = None
    # Optional congestion bucket ("low"|"medium"|"high") from spot_concentration,
    # attached by the consuming endpoint via load_congestion() — None when no row.
    congestion: str | None = None


@dataclass
class SimilarResultRow:
    query: SpotCardRow
    neighbors: list[tuple[SpotCardRow, float]]


@dataclass
class MoodTagRow:
    code: str
    name: str
    emoji: str


@dataclass
class SpotImageRow:
    origin_image_url: str
    small_image_url: str | None


@dataclass
class SpotIntroRow:
    """detailIntro2-derived display fields, normalized across contentTypeId.
    All optional; absent keys stay None. (관광 12/14/28: usetime/restdate/parking/
    infocenter; 음식점 39: firstmenu/treatmenu)."""

    usetime: str | None = None
    restdate: str | None = None
    parking: str | None = None
    infocenter: str | None = None
    firstmenu: str | None = None
    treatmenu: str | None = None


@dataclass
class SpotDetailRow:
    content_id: str
    title: str
    first_image_url: str | None
    addr1: str | None
    addr2: str | None
    mapx: float | None
    mapy: float | None
    overview: str | None
    homepage: str | None
    tel: str | None
    region_name: str | None
    sigungu_name: str | None
    detail_status: str
    moods: list[MoodTagRow]
    images: list[SpotImageRow]
    category: str | None = None  # lcls_systm3_nm (e.g. "사적지", "찻집")
    intro: SpotIntroRow | None = None


@dataclass
class RelatedSpotRow:
    name: str
    category: str | None
    region_name: str | None
    address: str | None
    rank: int | None
    content_id: str | None


@dataclass
class TrendingSpotRow:
    content_id: str
    title: str
    first_image_url: str | None
    addr1: str | None
    mapx: float | None
    mapy: float | None
    region_name: str | None
    concentration_rate: float
    rank: int
