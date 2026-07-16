"""SPT DTOs."""

from __future__ import annotations

from pydantic import BaseModel, field_validator

from app.core.kto_images import https_kto_image


class SpotCard(BaseModel):
    contentId: str
    title: str
    firstImageUrl: str | None = None
    addr1: str | None = None
    mapx: float | None = None
    mapy: float | None = None
    category: str | None = None

    @field_validator("firstImageUrl")
    @classmethod
    def _upgrade_first_image(cls, v: str | None) -> str | None:
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
