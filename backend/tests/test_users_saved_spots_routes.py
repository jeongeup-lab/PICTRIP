"""Integration tests for the saved-spot (bookmark) routes.

Routes live in USR but user_saved_spots + spot-card DB access goes through SPT
services (no cross-module model imports — ADR-0002 / ADR-0011).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
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
    email = f"saved-{uuid.uuid4().hex[:10]}@e.st"
    row = (
        await session.execute(
            text("INSERT INTO users (email, name) VALUES (:e, 'Saver') RETURNING id"),
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


async def _seed_hidden_spot(session: AsyncSession, content_id: str) -> None:
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, first_image_url, addr1, "
            "mapx, mapy, show_flag) "
            "VALUES (:cid, 12, :t, 'http://kto/first.jpg', 'addr1', 127.0, 37.5, 0) "
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


def _auth(user_id: int) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id=user_id)}"}


@pytest.mark.asyncio
async def test_save_returns_201(client: AsyncClient, override_db_and_seed: AsyncSession) -> None:
    uid = await _seed_user(override_db_and_seed)
    await _seed_spot(override_db_and_seed, "SAVE-1")

    resp = await client.post("/v1/users/me/saved/SAVE-1", headers=_auth(uid))

    assert resp.status_code == 201
    body = resp.json()
    assert body["error"] is None
    assert body["data"]["contentId"] == "SAVE-1"
    assert body["data"]["saved"] is True


@pytest.mark.asyncio
async def test_duplicate_save_is_idempotent_200(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    uid = await _seed_user(override_db_and_seed)
    await _seed_spot(override_db_and_seed, "SAVE-DUP")

    first = await client.post("/v1/users/me/saved/SAVE-DUP", headers=_auth(uid))
    assert first.status_code == 201

    again = await client.post("/v1/users/me/saved/SAVE-DUP", headers=_auth(uid))
    assert again.status_code == 200
    assert again.json()["data"]["saved"] is True


@pytest.mark.asyncio
async def test_save_unknown_spot_returns_404(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    uid = await _seed_user(override_db_and_seed)

    resp = await client.post("/v1/users/me/saved/ghost-spot", headers=_auth(uid))

    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


@pytest.mark.asyncio
async def test_unsave_removes(client: AsyncClient, override_db_and_seed: AsyncSession) -> None:
    uid = await _seed_user(override_db_and_seed)
    await _seed_spot(override_db_and_seed, "SAVE-DEL")

    await client.post("/v1/users/me/saved/SAVE-DEL", headers=_auth(uid))

    deleted = await client.delete("/v1/users/me/saved/SAVE-DEL", headers=_auth(uid))
    assert deleted.status_code == 204
    assert deleted.content == b""

    listed = await client.get("/v1/users/me/saved", headers=_auth(uid))
    ids = [c["contentId"] for c in listed.json()["data"]]
    assert "SAVE-DEL" not in ids


@pytest.mark.asyncio
async def test_unsave_missing_is_idempotent_204(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    uid = await _seed_user(override_db_and_seed)
    await _seed_spot(override_db_and_seed, "SAVE-NONE")

    resp = await client.delete("/v1/users/me/saved/SAVE-NONE", headers=_auth(uid))
    assert resp.status_code == 204
    assert resp.content == b""


@pytest.mark.asyncio
async def test_list_returns_saved_spot_cards(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    uid = await _seed_user(override_db_and_seed)
    await _seed_spot(override_db_and_seed, "SAVE-A")
    await _seed_spot(override_db_and_seed, "SAVE-B")

    await client.post("/v1/users/me/saved/SAVE-A", headers=_auth(uid))
    await client.post("/v1/users/me/saved/SAVE-B", headers=_auth(uid))

    resp = await client.get("/v1/users/me/saved", headers=_auth(uid))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert {c["contentId"] for c in data} == {"SAVE-A", "SAVE-B"}
    card = data[0]
    # SPT spot-card shape
    assert {"contentId", "title", "firstImageUrl", "addr1", "mapx", "mapy"} <= set(card)


@pytest.mark.asyncio
async def test_list_returns_pagination_meta(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    uid = await _seed_user(override_db_and_seed)
    await _seed_spot(override_db_and_seed, "PAG-A")
    await client.post("/v1/users/me/saved/PAG-A", headers=_auth(uid))

    resp = await client.get("/v1/users/me/saved", headers=_auth(uid))
    assert resp.status_code == 200
    pag = resp.json()["meta"]["pagination"]
    assert pag["count"] == 1
    assert pag["hasMore"] is False
    assert pag["nextCursor"] is None


@pytest.mark.asyncio
async def test_list_paginates_with_cursor(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    uid = await _seed_user(override_db_and_seed)
    # Seed 30 saved spots so a limit=24 page has a next cursor.
    for i in range(30):
        cid = f"CUR-{i:03d}"
        await _seed_spot(override_db_and_seed, cid)
        await _insert_saved_row(override_db_and_seed, user_id=uid, content_id=cid)

    r1 = await client.get("/v1/users/me/saved?limit=24", headers=_auth(uid))
    assert r1.status_code == 200
    body1 = r1.json()
    meta1 = body1["meta"]["pagination"]
    assert meta1["count"] == 24
    assert meta1["hasMore"] is True
    assert meta1["nextCursor"]
    page1_ids = [c["contentId"] for c in body1["data"]]

    r2 = await client.get(
        f"/v1/users/me/saved?limit=24&cursor={meta1['nextCursor']}", headers=_auth(uid)
    )
    assert r2.status_code == 200
    body2 = r2.json()
    meta2 = body2["meta"]["pagination"]
    assert meta2["count"] == 6
    assert meta2["hasMore"] is False
    assert meta2["nextCursor"] is None
    page2_ids = [c["contentId"] for c in body2["data"]]

    # No overlap, full coverage.
    assert set(page1_ids).isdisjoint(page2_ids)
    assert len(set(page1_ids) | set(page2_ids)) == 30


@pytest.mark.asyncio
async def test_list_invalid_cursor_returns_422(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    uid = await _seed_user(override_db_and_seed)
    resp = await client.get("/v1/users/me/saved?cursor=not-a-real-cursor", headers=_auth(uid))
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_FAILED"


@pytest.mark.asyncio
async def test_list_limit_out_of_range_returns_422(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    uid = await _seed_user(override_db_and_seed)
    resp = await client.get("/v1/users/me/saved?limit=61", headers=_auth(uid))
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_is_user_scoped(client: AsyncClient, override_db_and_seed: AsyncSession) -> None:
    owner = await _seed_user(override_db_and_seed)
    other = await _seed_user(override_db_and_seed)
    await _seed_spot(override_db_and_seed, "SAVE-OWNER")

    await client.post("/v1/users/me/saved/SAVE-OWNER", headers=_auth(owner))

    resp = await client.get("/v1/users/me/saved", headers=_auth(other))
    assert resp.status_code == 200
    assert resp.json()["data"] == []


@pytest.mark.asyncio
async def test_save_without_auth_returns_401(client: AsyncClient) -> None:
    resp = await client.post("/v1/users/me/saved/SAVE-X")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "AUTH_TOKEN_INVALID"


@pytest.mark.asyncio
async def test_list_without_auth_returns_401(client: AsyncClient) -> None:
    resp = await client.get("/v1/users/me/saved")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "AUTH_TOKEN_INVALID"


@pytest.mark.asyncio
async def test_save_hidden_spot_returns_404(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    # A spot with show_flag=0 must be unsavable: GET /spots/{id} 404s on it, so
    # allowing a save would create a dead-end card. Same path as an unknown spot.
    uid = await _seed_user(override_db_and_seed)
    await _seed_hidden_spot(override_db_and_seed, "SAVE-HIDDEN")

    resp = await client.post("/v1/users/me/saved/SAVE-HIDDEN", headers=_auth(uid))

    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


@pytest.mark.asyncio
async def test_list_excludes_now_hidden_saved_spot(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    # A spot saved while visible, then later hidden (show_flag=0), must drop out
    # of the saved list — otherwise the card dead-ends on GET /spots/{id} 404.
    # Insert the join row directly so we bypass the save-time guard.
    uid = await _seed_user(override_db_and_seed)
    await _seed_spot(override_db_and_seed, "SAVE-VISIBLE")
    await _seed_hidden_spot(override_db_and_seed, "SAVE-GONE")
    await _insert_saved_row(override_db_and_seed, user_id=uid, content_id="SAVE-VISIBLE")
    await _insert_saved_row(override_db_and_seed, user_id=uid, content_id="SAVE-GONE")

    resp = await client.get("/v1/users/me/saved", headers=_auth(uid))

    assert resp.status_code == 200
    ids = {c["contentId"] for c in resp.json()["data"]}
    assert ids == {"SAVE-VISIBLE"}
