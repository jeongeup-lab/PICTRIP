"""MAP DTOs."""

from __future__ import annotations

from pydantic import BaseModel, field_validator

from app.core.kto_images import https_kto_image


class CrowdInfo(BaseModel):
    contentId: str
    rate: float
    level: str  # easy | normal | crowded


class NearbyCrowd(BaseModel):
    rate: float
    level: str  # easy | normal | crowded


class NearbySpotCard(BaseModel):
    contentId: str
    title: str
    firstImageUrl: str | None = None
    firstImage2Url: str | None = None
    addr1: str | None = None
    mapx: float | None = None
    mapy: float | None = None
    dist: float | None = None  # distance from query point, metres
    category: str | None = None  # attraction|food|cafe|leisure|shopping|null
    overview: str | None = None  # KTO overview(verbatim) — null when not yet cached
    crowd: NearbyCrowd | None = None  # None when no crowd metric is cached

    @field_validator("firstImageUrl", "firstImage2Url")
    @classmethod
    def _upgrade_first_image(cls, v: str | None) -> str | None:
        return https_kto_image(v)


class RegionLabel(BaseModel):
    sido: str | None = None
    sigungu: str | None = None
    dong: str | None = None
    label: str
