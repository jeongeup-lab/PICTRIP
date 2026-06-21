"""USR domain DTOs. Owned by Dev A."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr


class UserPublic(BaseModel):
    id: int
    email: EmailStr | None = None
    name: str | None = None
    profileImageUrl: str | None = None
    isOnboarded: bool = False
    createdAt: datetime | None = None


class OAuthLoginIn(BaseModel):
    idToken: str
    nonce: str | None = None


class RefreshBody(BaseModel):
    refreshToken: str


class LogoutBody(BaseModel):
    refreshToken: str | None = None


class TokenPair(BaseModel):
    accessToken: str
    refreshToken: str
    expiresIn: int
    user: UserPublic


class SavedSpotToggle(BaseModel):
    """Result of save/unsave on a spot bookmark (ADR-0011)."""

    contentId: str
    saved: bool
