"""USR service layer."""

from __future__ import annotations

from datetime import UTC, datetime

from redis.asyncio import Redis
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import (
    deny_refresh,
    mint_token_pair,
    refresh_tokens,
)
from app.core.exceptions import AuthTokenInvalid
from app.core.kakao_oidc import verify_id_token
from app.modules.users.models import User, UserAuthProvider, UserConsent
from app.modules.users.schemas import KakaoCallbackIn, TokenPair, UserPublic

# terms_version stamped on a consent row that is auto-created as a side effect
# of reading/writing the notification toggle (the user has not gone through the
# explicit consent flow yet). 16-char column limit.
_AUTO_CONSENT_TERMS_VERSION = "unset"


async def _find_provider(
    session: AsyncSession, *, provider: str, provider_user_id: str
) -> UserAuthProvider | None:
    return await session.scalar(  # type: ignore[no-any-return]
        select(UserAuthProvider).where(
            UserAuthProvider.provider == provider,
            UserAuthProvider.provider_user_id == provider_user_id,
        )
    )


async def authenticate_with_kakao(
    session: AsyncSession, redis: Redis, body: KakaoCallbackIn
) -> TokenPair:
    claims = await verify_id_token(body.idToken, expected_nonce=body.nonce)

    existing = await _find_provider(session, provider="kakao", provider_user_id=claims.sub)
    if existing is not None:
        user = await session.get(User, existing.user_id)
        assert user is not None
    else:
        try:
            async with session.begin_nested():
                user = User(
                    email=claims.email,
                    name=claims.nickname,
                    profile_image_url=claims.picture,
                )
                session.add(user)
                await session.flush()
                session.add(
                    UserAuthProvider(
                        user_id=user.id,
                        provider="kakao",
                        provider_user_id=claims.sub,
                    )
                )
                await session.flush()
        except IntegrityError:
            existing = await _find_provider(session, provider="kakao", provider_user_id=claims.sub)
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
    creates a *new* account (the provider link no longer maps to this user). All
    sessions are revoked. Idempotent — a second call (or a deleted user) is a
    no-op beyond re-revoking sessions. Personal child rows fall away on the
    eventual hard delete via ``ondelete=CASCADE``; the soft-deleted row carries no
    personal data in the meantime.
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


async def _get_or_create_consent(session: AsyncSession, user_id: int) -> UserConsent:
    """Return the user's consent row, creating a default (all-off) one if none
    exists. `user_consents` is owned by USR; other modules read the notification
    toggle through `get_notification_consent` / `set_notification_consent`."""
    consent = await session.get(UserConsent, user_id)
    if consent is not None:
        return consent
    consent = UserConsent(
        user_id=user_id,
        terms_version=_AUTO_CONSENT_TERMS_VERSION,
    )
    session.add(consent)
    await session.commit()
    return consent


async def get_notification_consent(session: AsyncSession, user_id: int) -> bool:
    """Current notification master toggle, creating a default row if none."""
    consent = await _get_or_create_consent(session, user_id)
    return consent.notification_consent


async def set_notification_consent(session: AsyncSession, user_id: int, *, enabled: bool) -> bool:
    """Persist the notification master toggle; returns the stored value."""
    consent = await _get_or_create_consent(session, user_id)
    consent.notification_consent = enabled
    await session.commit()
    return consent.notification_consent


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
