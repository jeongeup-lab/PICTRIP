"""USR service layer."""

from __future__ import annotations

from datetime import UTC, datetime

from redis.asyncio import Redis

from app.core.auth import (
    deny_refresh,
    mint_token_pair,
    refresh_tokens,
)
from app.core.db import AsyncSession
from app.core.exceptions import AuthTokenInvalid
from app.core.oidc import verify_oauth_id_token
from app.modules.users import repositories as repo
from app.modules.users.schemas import (
    ConsentIn,
    ConsentOut,
    ConsentState,
    OAuthLoginIn,
    TokenPair,
    UserPublic,
)


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
    # Real account deletion to satisfy App Store/Play 5.1.1(v): scrub PII + unlink
    # OAuth so re-login with the same identity creates a fresh account. Idempotent.
    user = await repo.get_user(session, user_id)
    if user is not None and user.deleted_at is None:
        user.email = None
        user.name = None
        user.bio = None
        user.location_label = None
        user.profile_image_url = None
        user.taste_vector = None
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
