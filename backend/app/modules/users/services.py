"""USR service layer."""

from __future__ import annotations

from datetime import UTC, datetime

from redis.asyncio import Redis
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import (
    deny_refresh,
    mint_token_pair,
    refresh_tokens,
)
from app.core.exceptions import AuthTokenInvalid
from app.core.oidc import verify_oauth_id_token
from app.modules.users.models import User, UserAuthProvider, UserConsent
from app.modules.users.schemas import ConsentIn, ConsentOut, OAuthLoginIn, TokenPair, UserPublic


async def _find_provider(
    session: AsyncSession, *, provider: str, provider_user_id: str
) -> UserAuthProvider | None:
    return await session.scalar(  # type: ignore[no-any-return]
        select(UserAuthProvider).where(
            UserAuthProvider.provider == provider,
            UserAuthProvider.provider_user_id == provider_user_id,
        )
    )


async def authenticate_with_oauth(
    session: AsyncSession, provider: str, body: OAuthLoginIn
) -> TokenPair:
    """Verify a provider OIDC id_token, upsert the user + provider link, mint a
    token pair. Identity key = provider + sub (S09 §3.1). Zero Redis writes."""
    claims = await verify_oauth_id_token(provider, body.idToken, expected_nonce=body.nonce)

    existing = await _find_provider(session, provider=provider, provider_user_id=claims.sub)
    if existing is not None:
        user = await session.get(User, existing.user_id)
        assert user is not None
    else:
        try:
            async with session.begin_nested():
                user = User(
                    email=claims.email,
                    name=claims.name,
                    profile_image_url=claims.picture,
                )
                session.add(user)
                await session.flush()
                session.add(
                    UserAuthProvider(
                        user_id=user.id,
                        provider=provider,
                        provider_user_id=claims.sub,
                    )
                )
                await session.flush()
        except IntegrityError:
            existing = await _find_provider(session, provider=provider, provider_user_id=claims.sub)
            assert existing is not None, "savepoint rollback but provider not found"
            user = await session.get(User, existing.user_id)
            assert user is not None

    await session.commit()

    user_public = UserPublic(
        id=user.id,
        email=user.email,
        name=user.name,
        profileImageUrl=user.profile_image_url,
        isOnboarded=False,
        createdAt=user.created_at,
    )
    return mint_token_pair(user_id=user.id, user=user_public)


async def get_user_public(session: AsyncSession, user_id: int) -> UserPublic:
    user = await session.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise AuthTokenInvalid()
    return UserPublic(
        id=user.id,
        email=user.email,
        name=user.name,
        profileImageUrl=user.profile_image_url,
        isOnboarded=False,
        createdAt=user.created_at,
    )


async def delete_user_account(session: AsyncSession, redis: Redis, user_id: int) -> None:
    """회원 탈퇴 — App Store/Play 심사 가이드(5.1.1(v))를 만족하는 실제 계정 삭제.

    Soft-delete (``deleted_at``) keeps the row for referential integrity, but PII
    is scrubbed and OAuth links are removed so the account is genuinely gone, not
    merely deactivated: re-logging-in with the same Kakao/Google/Apple identity
    creates a *new* account (the provider link no longer maps to this user).
    Idempotent — a second call (or a deleted user) is a no-op. Personal child rows
    fall away on the eventual hard delete via ``ondelete=CASCADE``; the
    soft-deleted row carries no personal data in the meantime.
    """
    user = await session.get(User, user_id)
    if user is not None and user.deleted_at is None:
        user.email = None
        user.name = None
        user.bio = None
        user.location_label = None
        user.profile_image_url = None
        user.taste_vector = None
        user.deleted_at = datetime.now(tz=UTC)
        # Unlink OAuth identities so the provider account can start fresh.
        await session.execute(delete(UserAuthProvider).where(UserAuthProvider.user_id == user_id))
        await session.commit()
    # Denylist model: no session table to revoke. Account safety rests on
    # `deleted_at` (get_user_public rejects a deleted user, so a refresh can't
    # re-hydrate) plus the ≤15-min access-token expiry.


async def put_consents(session: AsyncSession, user_id: int, body: ConsentIn) -> ConsentOut:
    """Upsert the user's consent row (PK = user_id), stamping ``consented_at``.

    Idempotent: a repeat PUT updates the same row in place via
    ``INSERT … ON CONFLICT (user_id) DO UPDATE``. The dropped-from-ORM
    ``notification_consent`` DB column is never referenced (it has a DB default),
    so omitting it from the INSERT is safe (expand/contract — M3 / Task 20)."""
    stmt = (
        pg_insert(UserConsent)
        .values(
            user_id=user_id,
            location_consent=body.locationConsent,
            photo_consent=body.photoConsent,
            terms_version=body.termsVersion,
            consented_at=func.now(),
        )
        .on_conflict_do_update(
            index_elements=[UserConsent.user_id],
            set_={
                "location_consent": body.locationConsent,
                "photo_consent": body.photoConsent,
                "terms_version": body.termsVersion,
                "consented_at": func.now(),
            },
        )
        .returning(
            UserConsent.location_consent,
            UserConsent.photo_consent,
            UserConsent.terms_version,
            UserConsent.consented_at,
        )
    )
    row = (await session.execute(stmt)).one()
    await session.commit()
    return ConsentOut(
        locationConsent=row.location_consent,
        photoConsent=row.photo_consent,
        termsVersion=row.terms_version,
        consentedAt=row.consented_at,
    )


async def refresh_session(session: AsyncSession, redis: Redis, refresh_token: str) -> TokenPair:
    # `refresh_tokens` is a core token primitive and only knows the user id, so
    # the pair it returns carries a minimal `UserPublic(id=…)`. Re-hydrate the
    # full profile from the DB so a refresh doesn't wipe name/email/profileImage
    # in the mobile store — refresh must return the same shape as login.
    pair = await refresh_tokens(redis, refresh_token)
    pair.user = await get_user_public(session, pair.user.id)
    return pair


async def logout_session(redis: Redis, refresh_token: str | None) -> None:
    """Idempotent: missing/malformed/expired tokens are silently no-ops."""
    await deny_refresh(redis, refresh_token)
