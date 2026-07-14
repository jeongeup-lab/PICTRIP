from __future__ import annotations

from pydantic import BaseModel, field_validator

from app.core.kto_images import hires_kto_image, https_kto_image


class OverseasPost(BaseModel):
    id: int
    nameKo: str
    countryCode: str
    countryNameKo: str
    descriptionKo: str | None
    imageUrl: str
    imageAuthor: str | None
    imageLicense: str | None
    imageLicenseUrl: str | None
    imageSourceUrl: str


class PostsResponse(BaseModel):
    seed: str
    items: list[OverseasPost]
    nextCursor: str | None
    hasMore: bool


class MatchCard(BaseModel):
    contentId: str
    title: str
    regionLabel: str
    imageUrl: str
    overviewFirst: str | None

    @field_validator("imageUrl")
    @classmethod
    def _upgrade_image(cls, v: str) -> str:
        return hires_kto_image(v) or v


class MatchesResponse(BaseModel):
    overseasId: int
    matches: list[MatchCard]


class ChannelCard(BaseModel):
    contentId: str | None
    title: str
    regionLabel: str
    imageUrl: str | None
    dist: float | None = None
    rank: int | None = None
    dday: str | None = None
    line: str | None = None
    tag: str | None = None
    saveable: bool = True

    @field_validator("imageUrl")
    @classmethod
    def _upgrade_image(cls, v: str | None) -> str | None:
        return hires_kto_image(v) or v


class ChannelCardsResponse(BaseModel):
    key: str
    label: str
    cards: list[ChannelCard]


class ChannelMeta(BaseModel):
    key: str
    label: str
    thumbnailUrl: str | None
    available: bool

    @field_validator("thumbnailUrl")
    @classmethod
    def _upgrade_thumbnail(cls, v: str | None) -> str | None:
        return https_kto_image(v) or v


class ChannelsResponse(BaseModel):
    channels: list[ChannelMeta]
