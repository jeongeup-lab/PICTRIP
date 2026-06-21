"""Task 14: GET /v1/users/me serialization (displayName/avatarUrl) +
GET /v1/users/me/saved cursor pagination.

Mirrors tests/test_users_saved_spots_routes.py: a per-test override binds the
FastAPI ``get_db`` dependency and the seed session to one connection wrapped in
an outer transaction that is rolled back on teardown. Auth is exercised
end-to-end with a real user row + a real access token.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.core.auth import create_access_token
from app.main import app


@pytest_asyncio.fixture(autouse=True)
async def override_db_and_seed() -> AsyncIterator[AsyncSession]:
    from app.core.db import get_db

    eng = create_async_engine(str(settings.sqlalchemy_database_url), poolclass=NullPool)
    async with eng.connect() as conn:
        tx = await conn.begin()
        try:
            seed = AsyncSession(
                bind=conn,
                expire_on_commit=False,
                join_transaction_mode="create_savepoint",
            )

            async def _override() -> AsyncIterator[AsyncSession]:
                session = AsyncSession(
                    bind=conn,
                    expire_on_commit=False,
                    join_transaction_mode="create_savepoint",
                )
                try:
                    yield session
                finally:
                    await session.close()

            app.dependency_overrides[get_db] = _override
            try:
                yield seed
            finally:
                await seed.close()
                app.dependency_overrides.pop(get_db, None)
        finally:
            if tx.is_active:
                await tx.rollback()
    await eng.dispose()


async def _seed_user(session: AsyncSession) -> int:
    email = f"me-{uuid.uuid4().hex[:10]}@e.st"
    row = (
        await session.execute(
            text(
                "INSERT INTO users (email, name, profile_image_url) "
                "VALUES (:e, 'Trip Lee', 'http://kto/avatar.jpg') RETURNING id"
            ),
            {"e": email},
        )
    ).first()
    assert row is not None
    await session.commit()
    return int(row.id)


async def _seed_spot(session: AsyncSession, content_id: str) -> None:
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, first_image_url, addr1, "
            "mapx, mapy, show_flag) "
            "VALUES (:cid, 12, :t, 'http://kto/first.jpg', 'addr1', 127.0, 37.5, 1) "
            "ON CONFLICT (content_id) DO NOTHING"
        ),
        {"cid": content_id, "t": f"title-{content_id}"},
    )
    await session.commit()


async def _insert_saved_row(session: AsyncSession, *, user_id: int, content_id: str) -> None:
    await session.execute(
        text(
            "INSERT INTO user_saved_spots (user_id, content_id) VALUES (:u, :c) "
            "ON CONFLICT (user_id, content_id) DO NOTHING"
        ),
        {"u": user_id, "c": content_id},
    )
    await session.commit()


async def _seed_many_saved(session: AsyncSession, *, user_id: int, n: int) -> None:
    for i in range(n):
        cid = f"MANY-{i:03d}"
        await _seed_spot(session, cid)
        await _insert_saved_row(session, user_id=user_id, content_id=cid)


def _auth(user_id: int) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id=user_id)}"}


async def test_me_uses_display_name_avatar_url(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    uid = await _seed_user(override_db_and_seed)
    r = await client.get("/v1/users/me", headers=_auth(uid))
    assert r.status_code == 200
    body = r.json()["data"]
    assert body["displayName"] == "Trip Lee"
    assert body["avatarUrl"] == "http://kto/avatar.jpg"
    assert "name" not in body and "profileImageUrl" not in body


async def test_saved_paginates_with_cursor(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    uid = await _seed_user(override_db_and_seed)
    await _seed_many_saved(override_db_and_seed, user_id=uid, n=30)

    r1 = await client.get("/v1/users/me/saved?limit=24", headers=_auth(uid))
    assert r1.status_code == 200
    meta = r1.json()["meta"]["pagination"]
    assert meta["hasMore"] is True
    assert meta["nextCursor"]
    assert meta["count"] == 24

    r2 = await client.get(
        f"/v1/users/me/saved?limit=24&cursor={meta['nextCursor']}", headers=_auth(uid)
    )
    assert r2.status_code == 200
    meta2 = r2.json()["meta"]["pagination"]
    assert meta2["count"] == 6
    assert meta2["hasMore"] is False
    assert meta2["nextCursor"] is None


async def test_saved_default_limit_is_24(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    uid = await _seed_user(override_db_and_seed)
    await _seed_many_saved(override_db_and_seed, user_id=uid, n=30)

    r = await client.get("/v1/users/me/saved", headers=_auth(uid))
    assert r.status_code == 200
    assert len(r.json()["data"]) == 24


async def test_saved_card_shape_is_canonical(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    uid = await _seed_user(override_db_and_seed)
    await _seed_spot(override_db_and_seed, "SHAPE-1")
    await _insert_saved_row(override_db_and_seed, user_id=uid, content_id="SHAPE-1")

    r = await client.get("/v1/users/me/saved", headers=_auth(uid))
    card = r.json()["data"][0]
    assert {
        "contentId",
        "title",
        "firstImageUrl",
        "addr1",
        "mapx",
        "mapy",
        "category",
        "congestion",
    } <= set(card)
