from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, patch

import jwt
import pytest
from fakeredis.aioredis import FakeRedis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthSessionRevoked, AuthTokenInvalid
from app.core.oidc import OidcClaims
from app.modules.users.models import User, UserAuthProvider
from app.modules.users.schemas import OAuthLoginIn
from app.modules.users.services import (
    authenticate_with_oauth,
    get_user_public,
    logout_session,
    refresh_session,
)


@pytest.mark.asyncio
async def test_authenticate_with_oauth_new_signup_creates_user(db_session: AsyncSession) -> None:
    fake_claims = OidcClaims(sub="kakao-user-1", email=None, name="Hong", picture=None)
    with patch(
        "app.modules.users.services.verify_oauth_id_token",
        AsyncMock(return_value=fake_claims),
    ):
        pair = await authenticate_with_oauth(db_session, "kakao", OAuthLoginIn(idToken="x"))
    assert pair.user.displayName == "Hong"
    rows = (await db_session.scalars(select(User))).all()
    assert len(rows) == 1


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
    # Identity key is provider + sub: the same sub on kakao vs google → two users.
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
async def test_authenticate_with_oauth_savepoint_rollback_on_race(
    db_session: AsyncSession,
) -> None:
    """Force the IntegrityError path: the pre-check is mocked to miss the first
    time (simulating concurrent race where the other transaction hasn't committed
    yet), so the service enters the savepoint, the UserAuthProvider INSERT
    collides with a pre-existing row, savepoint rolls back the orphan User
    insert, and the reselect picks up the winning row."""

    # Pre-populate a winning row (the "other transaction" already committed).
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
            return None  # first call: pretend no row exists yet (race window)
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

    # The reselect after savepoint rollback returned the WINNING user.
    assert pair.user.id == winner.id

    # Exactly one User and one UserAuthProvider — the orphan User insert was
    # rolled back by the savepoint.
    users = (await db_session.scalars(select(User))).all()
    providers = (await db_session.scalars(select(UserAuthProvider))).all()
    assert len(users) == 1
    assert len(providers) == 1
    assert users[0].id == winner.id

    # The fake was called twice: once before savepoint (returned None),
    # once after IntegrityError to reselect (returned the row).
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
    # Sliding refresh, no rotation: the new refresh carries the SAME jti.
    old_jti = jwt.decode(pair.refreshToken, options={"verify_signature": False})["jti"]
    new_jti = jwt.decode(new_pair.refreshToken, options={"verify_signature": False})["jti"]
    assert new_jti == old_jti
    # Refresh must return the full profile, not a minimal id-only UserPublic.
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
    # Denylist model: logout adds denyjti:{jti}; a subsequent refresh is rejected.
    jti = jwt.decode(pair.refreshToken, options={"verify_signature": False})["jti"]
    assert await redis_client_fake.exists(f"denyjti:{jti}") == 1
    with pytest.raises(AuthSessionRevoked):
        await refresh_session(db_session, redis_client_fake, pair.refreshToken)


@pytest.mark.asyncio
async def test_logout_session_with_none_is_noop(redis_client_fake: FakeRedis) -> None:
    # Must not raise — no side effects.
    await logout_session(redis_client_fake, None)


@pytest.mark.asyncio
async def test_logout_session_with_garbage_is_noop(redis_client_fake: FakeRedis) -> None:
    # Must not raise — no side effects.
    await logout_session(redis_client_fake, "not-a-jwt")


# ---------------------------------------------------------------------------
# get_user_public
# ---------------------------------------------------------------------------


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
