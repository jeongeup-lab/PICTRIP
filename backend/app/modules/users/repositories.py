from __future__ import annotations

from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import User, UserAuthProvider, UserConsent
from app.modules.users.nickname import generate_nickname


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

    user_email = email
    if user_email is not None and await get_active_user_by_email(session, user_email) is not None:
        user_email = None

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
        existing = await find_auth_provider(
            session, provider=provider, provider_user_id=provider_user_id
        )
        if existing is None:
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


async def list_provider_refresh_tokens(
    session: AsyncSession, user_id: int, *, provider: str
) -> list[str]:
    rows = await session.scalars(
        select(UserAuthProvider.provider_refresh_token).where(
            UserAuthProvider.user_id == user_id,
            UserAuthProvider.provider == provider,
            UserAuthProvider.provider_refresh_token.is_not(None),
        )
    )
    return [token for token in rows.all() if token]


async def set_provider_refresh_token(
    session: AsyncSession, *, user_id: int, provider: str, provider_user_id: str, token: str
) -> None:
    row = await session.scalar(
        select(UserAuthProvider).where(
            UserAuthProvider.user_id == user_id,
            UserAuthProvider.provider == provider,
            UserAuthProvider.provider_user_id == provider_user_id,
        )
    )
    if row is not None:
        row.provider_refresh_token = token


async def upsert_consent(
    session: AsyncSession,
    *,
    user_id: int,
    location_consent: bool,
    terms_version: str,
) -> Any:
    stmt = (
        pg_insert(UserConsent)
        .values(
            user_id=user_id,
            location_consent=location_consent,
            terms_version=terms_version,
            consented_at=func.now(),
        )
        .on_conflict_do_update(
            index_elements=[UserConsent.user_id],
            set_={
                "location_consent": location_consent,
                "terms_version": terms_version,
                "consented_at": func.now(),
            },
        )
        .returning(
            UserConsent.location_consent,
            UserConsent.terms_version,
            UserConsent.consented_at,
        )
    )
    return (await session.execute(stmt)).one()


async def get_consent(session: AsyncSession, user_id: int) -> UserConsent | None:
    return await session.get(UserConsent, user_id)


async def upsert_ai_transfer_consent(
    session: AsyncSession,
    *,
    user_id: int,
    granted: bool,
    version: str,
) -> Any:
    """위치·약관 동의를 건드리지 않는다 — 그쪽은 포커스마다 전체 PUT 으로 덮어써진다."""
    decided_at = func.now() if granted else None
    stmt = (
        pg_insert(UserConsent)
        .values(
            user_id=user_id,
            ai_transfer_consent=granted,
            ai_transfer_version=version if granted else None,
            ai_transfer_consented_at=decided_at,
        )
        .on_conflict_do_update(
            index_elements=[UserConsent.user_id],
            set_={
                "ai_transfer_consent": granted,
                "ai_transfer_version": version if granted else None,
                "ai_transfer_consented_at": decided_at,
            },
        )
        .returning(
            UserConsent.location_consent,
            UserConsent.terms_version,
            UserConsent.consented_at,
            UserConsent.ai_transfer_consent,
            UserConsent.ai_transfer_version,
            UserConsent.ai_transfer_consented_at,
        )
    )
    return (await session.execute(stmt)).one()
