"""MAP DTOs."""

from __future__ import annotations

from pydantic import BaseModel, field_validator

from app.core.kto_images import https_kto_image


class NearbySpotCard(BaseModel):
    contentId: str
    title: str
    firstImageUrl: str | None = None
    addr1: str | None = None
    mapx: float | None = None
    mapy: float | None = None
    dist: float | None = None  # distance from query point, metres
    category: str | None = None  # KTO subtype label (lcls_systm3_nm)
    regionName: str | None = None
    sigunguName: str | None = None
    overview: str | None = None  # KTO overview, verbatim

    @field_validator("firstImageUrl")
    @classmethod
    def _upgrade_first_image(cls, v: str | None) -> str | None:
        return https_kto_image(v)


class RegionLabel(BaseModel):
    sido: str | None = None
    sigungu: str | None = None
    dong: str | None = None
    label: str


class Centroid(BaseModel):
    lat: float
    lng: float


class SigunguNode(BaseModel):
    sigunguCode: str
    sigunguName: str
    centroid: Centroid


class RegionNode(BaseModel):
    regionCode: str
    regionName: str
    centroid: Centroid
    sigungus: list[SigunguNode]
