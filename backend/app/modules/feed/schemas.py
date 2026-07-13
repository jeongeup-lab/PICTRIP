from __future__ import annotations

from pydantic import BaseModel


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


class ChannelCardsResponse(BaseModel):
    key: str
    label: str
    cards: list[ChannelCard]


class ChannelMeta(BaseModel):
    key: str
    label: str
    thumbnailUrl: str | None
    available: bool


class ChannelsResponse(BaseModel):
    channels: list[ChannelMeta]
