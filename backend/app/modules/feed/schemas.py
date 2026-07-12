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
