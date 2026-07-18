from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, patch

import jwt
import pytest
from fakeredis.aioredis import FakeRedis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import User, UserAuthProvider
from app.modules.users.oidc import OidcClaims
from app.modules.users.schemas import OAuthLoginIn
from app.modules.users.services import (
    authenticate_with_oauth,
    get_user_public,
    logout_session,
    refresh_session,
)
from app.web.errors import AuthSessionRevoked, AuthTokenInvalid


@pytest.mark.asyncio
async def test_authenticate_with_oauth_new_signup_creates_user(db_session: AsyncSession) -> None:
    fake_claims = OidcClaims(sub="kakao-user-1", email=None, name="Hong", picture=None)
    with patch(
        "app.modules.users.services.verify_oauth_id_token",
        AsyncMock(return_value=fake_claims),
    ):
        pair = await authenticate_with_oauth(db_session, "kakao", OAuthLoginIn(idToken="x"))
    assert pair.user.displayName
    assert pair.user.displayName != "Hong"
    rows = (await db_session.scalars(select(User))).all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_authenticate_with_oauth_returning_user_name_unchanged(
    db_session: AsyncSession,
) -> None:
    fake_claims = OidcClaims(sub="kakao-user-keep", email=None, name="Ignored", picture=None)
    with patch(
        "app.modules.users.services.verify_oauth_id_token",
        AsyncMock(return_value=fake_claims),
    ):
        first = await authenticate_with_oauth(db_session, "kakao", OAuthLoginIn(idToken="x"))
        second = await authenticate_with_oauth(db_session, "kakao", OAuthLoginIn(idToken="x"))
    assert first.user.displayName
    assert second.user.displayName == first.user.displayName


@pytest.mark.asyncio
async def test_authenticate_with_oauth_returning_user_reuses_row(
    db_session: AsyncSession,
) -> None:
    fake_claims = OidcClaims(sub="kakao-user-2", email=None, name=None, picture=None)
    with patch(
        "app.modules.users.services.verify_oauth_id_token",
        AsyncMock(return_value=fake_claims),
    ):
        await authenticate_with_oauth(db_session, "kakao", OAuthLoginIn(idToken="x"))
        await authenticate_with_oauth(db_session, "kakao", OAuthLoginIn(idToken="x"))
    users = (await db_session.scalars(select(User))).all()
    providers = (await db_session.scalars(select(UserAuthProvider))).all()
    assert len(users) == 1
    assert len(providers) == 1


@pytest.mark.asyncio
async def test_authenticate_with_oauth_distinct_providers_same_sub_are_separate(
    db_session: AsyncSession,
) -> None:
    fake_claims = OidcClaims(sub="shared-sub", email=None, name=None, picture=None)
    with patch(
        "app.modules.users.services.verify_oauth_id_token",
        AsyncMock(return_value=fake_claims),
    ):
        await authenticate_with_oauth(db_session, "kakao", OAuthLoginIn(idToken="x"))
        await authenticate_with_oauth(db_session, "google", OAuthLoginIn(idToken="x"))
    users = (await db_session.scalars(select(User))).all()
    providers = (await db_session.scalars(select(UserAuthProvider))).all()
    assert len(users) == 2
    assert {p.provider for p in providers} == {"kakao", "google"}


@pytest.mark.asyncio
async def test_authenticate_with_oauth_email_collision_does_not_crash(
    db_session: AsyncSession,
) -> None:
    from app.modules.users.schemas import EmailSignupIn
    from app.modules.users.services import signup_with_email

    await signup_with_email(
        db_session,
        EmailSignupIn(email="dup@example.com", password="password123", name="Email User"),
    )

    fake_claims = OidcClaims(
        sub="google-dup", email="dup@example.com", name="Google User", picture=None
    )
    with patch(
        "app.modules.users.services.verify_oauth_id_token",
        AsyncMock(return_value=fake_claims),
    ):
        pair = await authenticate_with_oauth(db_session, "google", OAuthLoginIn(idToken="x"))

    users = (await db_session.scalars(select(User))).all()
    assert len(users) == 2
    oauth_user = next(u for u in users if u.id == pair.user.id)
    assert oauth_user.email is None
    providers = (await db_session.scalars(select(UserAuthProvider))).all()
    assert {p.provider for p in providers} == {"email", "google"}


@pytest.mark.asyncio
async def test_authenticate_with_oauth_savepoint_rollback_on_race(
    db_session: AsyncSession,
) -> None:

    winner = User(email=None, name="Winner")
    db_session.add(winner)
    await db_session.flush()
    db_session.add(
        UserAuthProvider(
            user_id=winner.id,
            provider="kakao",
            provider_user_id="kakao-race-1",
        )
    )
    await db_session.flush()

    fake_claims = OidcClaims(sub="kakao-race-1", email=None, name=None, picture=None)

    from app.modules.users import repositories as users_repo

    real_find = users_repo.find_auth_provider
    call_count = {"n": 0}

    async def lying_find(
        session: Any, *, provider: str, provider_user_id: str
    ) -> UserAuthProvider | None:
        call_count["n"] += 1
        if call_count["n"] == 1:
            return None
        return await real_find(session, provider=provider, provider_user_id=provider_user_id)

    with (
        patch(
            "app.modules.users.services.verify_oauth_id_token",
            AsyncMock(return_value=fake_claims),
        ),
        patch(
            "app.modules.users.repositories.find_auth_provider",
            side_effect=lying_find,
        ),
    ):
        pair = await authenticate_with_oauth(db_session, "kakao", OAuthLoginIn(idToken="x"))

    assert pair.user.id == winner.id

    users = (await db_session.scalars(select(User))).all()
    providers = (await db_session.scalars(select(UserAuthProvider))).all()
    assert len(users) == 1
    assert len(providers) == 1
    assert users[0].id == winner.id

    assert call_count["n"] == 2


@pytest.mark.asyncio
async def test_refresh_session_returns_new_pair(
    db_session: AsyncSession, redis_client_fake: FakeRedis
) -> None:
    fake_claims = OidcClaims(sub="kakao-user-r", email=None, name=None, picture=None)
    with patch(
        "app.modules.users.services.verify_oauth_id_token",
        AsyncMock(return_value=fake_claims),
    ):
        pair = await authenticate_with_oauth(db_session, "kakao", OAuthLoginIn(idToken="x"))
    new_pair = await refresh_session(db_session, redis_client_fake, pair.refreshToken)
    old_jti = jwt.decode(pair.refreshToken, options={"verify_signature": False})["jti"]
    new_jti = jwt.decode(new_pair.refreshToken, options={"verify_signature": False})["jti"]
    assert new_jti == old_jti
    assert new_pair.user.id == pair.user.id


@pytest.mark.asyncio
async def test_logout_session_valid_refresh_revokes(
    db_session: AsyncSession, redis_client_fake: FakeRedis
) -> None:
    fake_claims = OidcClaims(sub="kakao-user-l1", email=None, name=None, picture=None)
    with patch(
        "app.modules.users.services.verify_oauth_id_token",
        AsyncMock(return_value=fake_claims),
    ):
        pair = await authenticate_with_oauth(db_session, "kakao", OAuthLoginIn(idToken="x"))
    await logout_session(redis_client_fake, pair.refreshToken)
    jti = jwt.decode(pair.refreshToken, options={"verify_signature": False})["jti"]
    assert await redis_client_fake.exists(f"denyjti:{jti}") == 1
    with pytest.raises(AuthSessionRevoked):
        await refresh_session(db_session, redis_client_fake, pair.refreshToken)


@pytest.mark.asyncio
async def test_logout_session_with_none_is_noop(redis_client_fake: FakeRedis) -> None:
    await logout_session(redis_client_fake, None)


@pytest.mark.asyncio
async def test_logout_session_with_garbage_is_noop(redis_client_fake: FakeRedis) -> None:
    await logout_session(redis_client_fake, "not-a-jwt")


@pytest.mark.asyncio
async def test_get_user_public_returns_dto(db_session: AsyncSession) -> None:
    user = User(email="a@b.c", name="A")
    db_session.add(user)
    await db_session.flush()
    dto = await get_user_public(db_session, user.id)
    assert dto.id == user.id
    assert dto.email == "a@b.c"


@pytest.mark.asyncio
async def test_get_user_public_soft_deleted_raises(db_session: AsyncSession) -> None:
    user = User(email="d@e.f", name="D", deleted_at=datetime.now(tz=UTC))
    db_session.add(user)
    await db_session.flush()
    with pytest.raises(AuthTokenInvalid):
        await get_user_public(db_session, user.id)


@pytest.mark.asyncio
async def test_get_user_public_unknown_id_raises(db_session: AsyncSession) -> None:
    with pytest.raises(AuthTokenInvalid):
        await get_user_public(db_session, 99999)
