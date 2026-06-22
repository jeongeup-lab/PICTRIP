"""USR domain DTOs. Owned by Dev A."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class UserPublic(BaseModel):
    id: int
    displayName: str | None = None
    email: EmailStr | None = None
    avatarUrl: str | None = None
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


class ConsentIn(BaseModel):
    """Consent submission body for PUT /users/me/consents."""

    locationConsent: bool
    photoConsent: bool = False
    termsVersion: str


class ConsentOut(BaseModel):
    """Persisted consent state echoed back after an upsert."""

    model_config = ConfigDict(from_attributes=True)

    locationConsent: bool
    photoConsent: bool
    termsVersion: str
    consentedAt: datetime
