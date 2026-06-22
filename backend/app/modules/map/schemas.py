"""MAP DTOs."""

from __future__ import annotations

from typing import Literal

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
    # KTO subtype 라벨(lcls_systm_codes.lcls_systm3_nm, 예: "사적지", "찻집") — null 가능.
    category: str | None = None
    regionName: str | None = None  # regions.ldong_regn_nm — null when unmapped
    sigunguName: str | None = None  # sigungus.ldong_signgu_nm — null when unmapped
    overview: str | None = None  # KTO overview(verbatim) — null when not yet cached
    # spot_concentration 버킷(Task 9) — concentration 행이 없으면 null.
    congestion: Literal["low", "medium", "high"] | None = None

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
