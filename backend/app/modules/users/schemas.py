from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


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
    authorizationCode: str | None = None


class RefreshBody(BaseModel):
    refreshToken: str


class LogoutBody(BaseModel):
    refreshToken: str | None = None


class DeleteAccountBody(BaseModel):
    refreshToken: str | None = None
    reason: str | None = Field(default=None, max_length=64)


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
    termsVersion: str


class ConsentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    locationConsent: bool
    termsVersion: str
    consentedAt: datetime


class ConsentState(BaseModel):
    locationConsent: bool = False
    termsVersion: str | None = None
    consentedAt: datetime | None = None
