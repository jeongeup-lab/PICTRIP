"""USR DTOs."""

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


class EmailSignupIn(BaseModel):
    email: EmailStr
    # bcrypt input is capped at 72 bytes; mirror that as the max password length.
    password: str = Field(min_length=8, max_length=72)
    name: str | None = None


class EmailLoginIn(BaseModel):
    email: EmailStr
    # Cap at bcrypt's 72-byte limit (same as signup) so a huge string can't waste
    # a hash. No min_length: a too-short password stays a uniform 401 (credential
    # check), never a 422 that would behave differently from a wrong password.
    password: str = Field(max_length=72)


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
