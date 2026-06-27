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
    lcls_systm3_nm: str | None = None  # KTO subtype label; canonical card category


@dataclass
class SimilarResultRow:
    query: SpotCardRow
    neighbors: list[tuple[SpotCardRow, float]]


@dataclass
class SpotImageRow:
    origin_image_url: str
    small_image_url: str | None


@dataclass
class SpotIntroRow:
    """detailIntro2 display fields, normalized across contentTypeId. All optional."""

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
    images: list[SpotImageRow]
    category: str | None = None  # lcls_systm3_nm subtype label
    intro: SpotIntroRow | None = None


@dataclass
class RelatedSpotRow:
    name: str
    category: str | None
    region_name: str | None
    address: str | None
    rank: int | None
    content_id: str | None
