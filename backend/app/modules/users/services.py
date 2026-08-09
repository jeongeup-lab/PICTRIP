from __future__ import annotations

import logging
from datetime import UTC, datetime

from redis.asyncio import Redis

from app.core.db import AsyncSession
from app.modules.spots.services.saved import delete_all_saved_for_user
from app.modules.users import apple_tokens
from app.modules.users import repositories as repo
from app.modules.users.oidc import verify_oauth_id_token
from app.modules.users.schemas import (
    ConsentIn,
    ConsentOut,
    ConsentState,
    OAuthLoginIn,
    TokenPair,
    UserPublic,
)
from app.security.jwt import (
    deny_refresh,
    mint_token_pair,
    refresh_tokens,
)
from app.web.errors import AuthTokenInvalid

log = logging.getLogger("app.users.services")


async def authenticate_with_oauth(
    session: AsyncSession, provider: str, body: OAuthLoginIn
) -> TokenPair:
    claims = await verify_oauth_id_token(provider, body.idToken, expected_nonce=body.nonce)

    user = await repo.get_or_create_user_via_provider(
        session,
        provider=provider,
        provider_user_id=claims.sub,
        email=claims.email,
        picture=claims.picture,
    )

    if provider == "apple" and body.authorizationCode:
        refresh_token = await apple_tokens.exchange_authorization_code(body.authorizationCode)
        if refresh_token:
            await repo.set_provider_refresh_token(
                session,
                user_id=user.id,
                provider=provider,
                provider_user_id=claims.sub,
                token=refresh_token,
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


async def delete_user_account(
    session: AsyncSession,
    redis: Redis,
    user_id: int,
    refresh_token: str | None = None,
) -> None:
    user = await repo.get_user(session, user_id)
    if user is not None and user.deleted_at is None:
        apple_tokens_to_revoke = await repo.list_provider_refresh_tokens(
            session, user_id, provider="apple"
        )
        user.email = None
        user.name = None
        user.bio = None
        user.location_label = None
        user.profile_image_url = None
        user.taste_vector = None
        user.password_hash = None
        user.deleted_at = datetime.now(tz=UTC)
        await repo.delete_auth_providers(session, user_id)
        await delete_all_saved_for_user(session, user_id=user_id)
        await session.commit()
        for token in apple_tokens_to_revoke:
            try:
                await apple_tokens.revoke_refresh_token(token)
            except Exception:
                log.warning("apple: revoke raised during account deletion", exc_info=True)
    await deny_refresh(redis, refresh_token)


async def put_consents(session: AsyncSession, user_id: int, body: ConsentIn) -> ConsentOut:
    row = await repo.upsert_consent(
        session,
        user_id=user_id,
        location_consent=body.locationConsent,
        terms_version=body.termsVersion,
    )
    await session.commit()
    return ConsentOut(
        locationConsent=row.location_consent,
        termsVersion=row.terms_version,
        consentedAt=row.consented_at,
    )


async def get_consents(session: AsyncSession, user_id: int) -> ConsentState:
    row = await repo.get_consent(session, user_id)
    if row is None:
        return ConsentState()
    return ConsentState(
        locationConsent=row.location_consent,
        termsVersion=row.terms_version,
        consentedAt=row.consented_at,
    )


async def refresh_session(session: AsyncSession, redis: Redis, refresh_token: str) -> TokenPair:
    pair = await refresh_tokens(redis, refresh_token)
    pair.user = await get_user_public(session, pair.user.id)
    return pair


async def logout_session(redis: Redis, refresh_token: str | None) -> None:
    await deny_refresh(redis, refresh_token)
