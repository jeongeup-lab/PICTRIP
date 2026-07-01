"""USR repositories — DB queries; SQLAlchemy lives here."""

from __future__ import annotations

from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.nickname import generate_nickname
from app.modules.users.models import User, UserAuthProvider, UserConsent


async def find_auth_provider(
    session: AsyncSession, *, provider: str, provider_user_id: str
) -> UserAuthProvider | None:
    return await session.scalar(  # type: ignore[no-any-return]
        select(UserAuthProvider).where(
            UserAuthProvider.provider == provider,
            UserAuthProvider.provider_user_id == provider_user_id,
        )
    )


async def get_user(session: AsyncSession, user_id: int) -> User | None:
    return await session.get(User, user_id)


async def get_active_user_by_email(session: AsyncSession, email: str) -> User | None:
    return await session.scalar(  # type: ignore[no-any-return]
        select(User).where(User.email == email, User.deleted_at.is_(None))
    )


async def create_email_user(session: AsyncSession, *, email: str, password_hash: str) -> User:
    """Insert a User + its 'email' provider link inside a savepoint.

    The display name is a generated random Korean nickname — signup never adopts
    a caller-supplied name (product decision: everyone starts with a fresh alias).
    Raises ``IntegrityError`` if a concurrent insert wins the partial-unique email
    index / provider UNIQUE constraint; the caller maps that to a 409."""
    async with session.begin_nested():
        user = User(email=email, name=generate_nickname(), password_hash=password_hash)
        session.add(user)
        await session.flush()
        session.add(UserAuthProvider(user_id=user.id, provider="email", provider_user_id=email))
        await session.flush()
    return user


async def get_or_create_user_via_provider(
    session: AsyncSession,
    *,
    provider: str,
    provider_user_id: str,
    email: str | None,
    picture: str | None,
) -> User:
    existing = await find_auth_provider(
        session, provider=provider, provider_user_id=provider_user_id
    )
    if existing is not None:
        user = await session.get(User, existing.user_id)
        assert user is not None
        return user

    # The profile email here is non-essential — identity is provider+sub. If it
    # already belongs to another active account, storing it would violate the
    # partial-unique active-email index (idx_users_email_active) and 500. Drop it
    # instead. We deliberately do NOT auto-link to that account: emails are
    # unverified, so linking would let an attacker pre-register a victim's email
    # and hijack the victim's later OAuth login (pre-account hijacking).
    user_email = email
    if user_email is not None and await get_active_user_by_email(session, user_email) is not None:
        user_email = None

    # A brand-new account always gets a generated random Korean nickname — the
    # provider's name claim is deliberately ignored (returning users below keep
    # whatever name they already have).
    try:
        async with session.begin_nested():
            user = User(email=user_email, name=generate_nickname(), profile_image_url=picture)
            session.add(user)
            await session.flush()
            session.add(
                UserAuthProvider(
                    user_id=user.id,
                    provider=provider,
                    provider_user_id=provider_user_id,
                )
            )
            await session.flush()
    except IntegrityError:
        # Either a concurrent insert won the provider UNIQUE constraint, or an
        # active-email collision slipped past the pre-check above (a TOCTOU race
        # where the other account committed in between).
        existing = await find_auth_provider(
            session, provider=provider, provider_user_id=provider_user_id
        )
        if existing is None:
            # Not a provider race → it was the email index. Re-insert without the
            # conflicting profile email.
            async with session.begin_nested():
                user = User(email=None, name=generate_nickname(), profile_image_url=picture)
                session.add(user)
                await session.flush()
                session.add(
                    UserAuthProvider(
                        user_id=user.id,
                        provider=provider,
                        provider_user_id=provider_user_id,
                    )
                )
                await session.flush()
            return user
        user = await session.get(User, existing.user_id)
        assert user is not None
    return user


async def delete_auth_providers(session: AsyncSession, user_id: int) -> None:
    await session.execute(delete(UserAuthProvider).where(UserAuthProvider.user_id == user_id))


async def upsert_consent(
    session: AsyncSession,
    *,
    user_id: int,
    location_consent: bool,
    photo_consent: bool,
    terms_version: str,
) -> Any:
    stmt = (
        pg_insert(UserConsent)
        .values(
            user_id=user_id,
            location_consent=location_consent,
            photo_consent=photo_consent,
            terms_version=terms_version,
            consented_at=func.now(),
        )
        .on_conflict_do_update(
            index_elements=[UserConsent.user_id],
            set_={
                "location_consent": location_consent,
                "photo_consent": photo_consent,
                "terms_version": terms_version,
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
    return (await session.execute(stmt)).one()


async def get_consent(session: AsyncSession, user_id: int) -> UserConsent | None:
    return await session.get(UserConsent, user_id)
