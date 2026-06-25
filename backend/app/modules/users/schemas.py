"""USR DTOs."""

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
    contentId: str
    saved: bool


class ConsentIn(BaseModel):
    locationConsent: bool
    photoConsent: bool = False
    termsVersion: str


class ConsentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    locationConsent: bool
    photoConsent: bool
    termsVersion: str
    consentedAt: datetime


class ConsentState(BaseModel):
    locationConsent: bool = False
    photoConsent: bool = False
    termsVersion: str | None = None
    consentedAt: datetime | None = None
