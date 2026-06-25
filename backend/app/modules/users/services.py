"""USR service layer."""

from __future__ import annotations

from datetime import UTC, datetime

from redis.asyncio import Redis
from sqlalchemy.exc import IntegrityError

from app.core.auth import (
    deny_refresh,
    mint_token_pair,
    refresh_tokens,
)
from app.core.db import AsyncSession
from app.core.exceptions import (
    AuthTokenInvalid,
    EmailAlreadyRegistered,
    InvalidCredentials,
)
from app.core.oidc import verify_oauth_id_token
from app.core.passwords import hash_password, verify_password
from app.modules.users import repositories as repo
from app.modules.users.models import User
from app.modules.users.schemas import (
    ConsentIn,
    ConsentOut,
    ConsentState,
    EmailLoginIn,
    EmailSignupIn,
    OAuthLoginIn,
    TokenPair,
    UserPublic,
)

# A precomputed bcrypt hash of a random value. ``login_with_email`` runs a verify
# against this when the email is unknown so the missing-user and wrong-password
# paths take ~the same time (reduces a timing oracle for email enumeration).
_DUMMY_PASSWORD_HASH = hash_password("pictrip-dummy-not-a-real-password")


def _user_public(user: User) -> UserPublic:
    return UserPublic(
        id=user.id,
        displayName=user.name,
        email=user.email,
        avatarUrl=user.profile_image_url,
        isOnboarded=False,
        createdAt=user.created_at,
    )


def _normalize_email(email: str) -> str:
    return email.strip().lower()


async def authenticate_with_oauth(
    session: AsyncSession, provider: str, body: OAuthLoginIn
) -> TokenPair:
    # Identity key = provider + sub (S09 §3.1). Zero Redis writes.
    claims = await verify_oauth_id_token(provider, body.idToken, expected_nonce=body.nonce)

    user = await repo.get_or_create_user_via_provider(
        session,
        provider=provider,
        provider_user_id=claims.sub,
        email=claims.email,
        name=claims.name,
        picture=claims.picture,
    )
    await session.commit()

    user_public = UserPublic(
        id=user.id,
        displayName=user.name,
        email=user.email,
        avatarUrl=user.profile_image_url,
        isOnboarded=False,
        createdAt=user.created_at,
    )
    return mint_token_pair(user_id=user.id, user=user_public)


async def signup_with_email(session: AsyncSession, body: EmailSignupIn) -> TokenPair:
    """Create a new email/password account and mint a token pair.

    Identity key is provider='email' + the normalized email. A pre-check rejects
    a duplicate active email with 409; a concurrent race is caught via the
    partial-unique index / provider UNIQUE constraint (IntegrityError → 409)."""
    email = _normalize_email(body.email)

    if await repo.get_active_user_by_email(session, email) is not None:
        raise EmailAlreadyRegistered()

    try:
        user = await repo.create_email_user(
            session, email=email, name=body.name, password_hash=hash_password(body.password)
        )
    except IntegrityError as e:
        raise EmailAlreadyRegistered() from e

    await session.commit()
    return mint_token_pair(user_id=user.id, user=_user_public(user))


async def login_with_email(session: AsyncSession, body: EmailLoginIn) -> TokenPair:
    """Verify an email/password credential and mint a token pair.

    Unknown email, an account with no password set, or a bad password all raise
    the same ``InvalidCredentials`` (401) so the response can't distinguish
    them. A dummy verify on the missing-user path keeps timing roughly uniform."""
    email = _normalize_email(body.email)
    user = await repo.get_active_user_by_email(session, email)

    if user is None or user.password_hash is None:
        verify_password(body.password, _DUMMY_PASSWORD_HASH)  # equalize timing
        raise InvalidCredentials()

    if not verify_password(body.password, user.password_hash):
        raise InvalidCredentials()

    return mint_token_pair(user_id=user.id, user=_user_public(user))


async def get_user_public(session: AsyncSession, user_id: int) -> UserPublic:
    user = await repo.get_user(session, user_id)
    if user is None or user.deleted_at is not None:
        raise AuthTokenInvalid()
    return UserPublic(
        id=user.id,
        displayName=user.name,
        email=user.email,
        avatarUrl=user.profile_image_url,
        isOnboarded=False,
        createdAt=user.created_at,
    )


async def delete_user_account(session: AsyncSession, redis: Redis, user_id: int) -> None:
    """회원 탈퇴 — App Store/Play 심사 가이드(5.1.1(v))를 만족하는 실제 계정 삭제.

    Soft-delete (``deleted_at``) keeps the row for referential integrity, but PII
    is scrubbed, the password credential is cleared, and OAuth links are removed
    so the account is genuinely gone, not merely deactivated: re-logging-in with
    the same Kakao/Google/Apple identity creates a *new* account (the provider
    link no longer maps to this user) and the email login no longer has a
    credential to verify against.
    Idempotent — a second call (or a deleted user) is a no-op. Personal child rows
    fall away on the eventual hard delete via ``ondelete=CASCADE``; the
    soft-deleted row carries no personal data in the meantime.
    """
    user = await repo.get_user(session, user_id)
    if user is not None and user.deleted_at is None:
        user.email = None
        user.name = None
        user.bio = None
        user.location_label = None
        user.profile_image_url = None
        user.taste_vector = None
        user.password_hash = None
        user.deleted_at = datetime.now(tz=UTC)
        await repo.delete_auth_providers(session, user_id)
        await session.commit()


async def put_consents(session: AsyncSession, user_id: int, body: ConsentIn) -> ConsentOut:
    row = await repo.upsert_consent(
        session,
        user_id=user_id,
        location_consent=body.locationConsent,
        photo_consent=body.photoConsent,
        terms_version=body.termsVersion,
    )
    await session.commit()
    return ConsentOut(
        locationConsent=row.location_consent,
        photoConsent=row.photo_consent,
        termsVersion=row.terms_version,
        consentedAt=row.consented_at,
    )


async def get_consents(session: AsyncSession, user_id: int) -> ConsentState:
    row = await repo.get_consent(session, user_id)
    if row is None:
        return ConsentState()
    return ConsentState(
        locationConsent=row.location_consent,
        photoConsent=row.photo_consent,
        termsVersion=row.terms_version,
        consentedAt=row.consented_at,
    )


async def refresh_session(session: AsyncSession, redis: Redis, refresh_token: str) -> TokenPair:
    pair = await refresh_tokens(redis, refresh_token)
    # Re-hydrate the full profile so a refresh returns the same shape as login
    # (the token primitive only knows the user id).
    pair.user = await get_user_public(session, pair.user.id)
    return pair


async def logout_session(redis: Redis, refresh_token: str | None) -> None:
    # Idempotent: missing/malformed/expired tokens are silently no-ops.
    await deny_refresh(redis, refresh_token)
