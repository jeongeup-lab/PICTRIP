"""Integration tests for saved-course CRUD (CRS, auth required).

  POST   /v1/courses            — persist a chosen draft as a saved course
  GET    /v1/courses            — list my courses (newest-updated first)
  GET    /v1/courses/{id}       — course detail (ordered spot cards)
  DELETE /v1/courses/{id}       — delete my course

Mirrors tests/test_usr_saved_spots_routes.py: a per-test override binds the
FastAPI get_db dependency + the seed session to one connection in an outer
transaction rolled back on teardown. Auth is end-to-end via a real user row +
a real access token. Courses are scoped by user_id, so another user's course
reads as 404 (existence is not leaked).
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
    row = (
        await session.execute(
            text("INSERT INTO users (email, name) VALUES (:e, 'Courser') RETURNING id"),
            {"e": f"crs-{uuid.uuid4().hex[:10]}@e.st"},
        )
    ).first()
    assert row is not None
    await session.commit()
    return int(row.id)


async def _seed_spot(session: AsyncSession, content_id: str, *, show_flag: int = 1) -> None:
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, first_image_url, addr1, "
            "mapx, mapy, show_flag) "
            "VALUES (:cid, 12, :t, 'http://kto/first.jpg', 'addr', 127.0, 37.5, :sf) "
            "ON CONFLICT (content_id) DO NOTHING"
        ),
        {"cid": content_id, "t": f"title-{content_id}", "sf": show_flag},
    )
    await session.commit()


def _auth(user_id: int) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id=user_id)}"}


def _body(*content_ids: str, name: str = "내 코스") -> dict[str, object]:
    return {
        "name": name,
        "baseContentId": content_ids[0] if content_ids else None,
        "durationType": "day",
        "paceType": "normal",
        "companionType": "solo",
        "courseType": "efficient",
        "items": [{"contentId": c, "position": i} for i, c in enumerate(content_ids)],
    }


@pytest.mark.asyncio
async def test_create_returns_201_with_summary(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    uid = await _seed_user(override_db_and_seed)
    await _seed_spot(override_db_and_seed, "CR-1")
    await _seed_spot(override_db_and_seed, "CR-2")

    resp = await client.post("/v1/courses", json=_body("CR-1", "CR-2"), headers=_auth(uid))

    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["name"] == "내 코스"
    assert data["itemCount"] == 2
    assert data["courseType"] == "efficient"
    assert isinstance(data["id"], int)


@pytest.mark.asyncio
async def test_create_rejects_unknown_spot(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    uid = await _seed_user(override_db_and_seed)
    await _seed_spot(override_db_and_seed, "CR-OK")

    resp = await client.post("/v1/courses", json=_body("CR-OK", "CR-GHOST"), headers=_auth(uid))

    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_FAILED"


@pytest.mark.asyncio
async def test_create_rejects_hidden_spot(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    uid = await _seed_user(override_db_and_seed)
    await _seed_spot(override_db_and_seed, "CR-HID", show_flag=0)

    resp = await client.post("/v1/courses", json=_body("CR-HID"), headers=_auth(uid))

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_requires_at_least_one_item(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    uid = await _seed_user(override_db_and_seed)
    body = _body()  # no items
    resp = await client.post("/v1/courses", json=body, headers=_auth(uid))
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_returns_my_courses_newest_first(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    uid = await _seed_user(override_db_and_seed)
    await _seed_spot(override_db_and_seed, "CR-A")
    await _seed_spot(override_db_and_seed, "CR-B")
    first = await client.post("/v1/courses", json=_body("CR-A", name="첫째"), headers=_auth(uid))
    second = await client.post("/v1/courses", json=_body("CR-B", name="둘째"), headers=_auth(uid))
    assert first.status_code == 201 and second.status_code == 201

    resp = await client.get("/v1/courses", headers=_auth(uid))

    assert resp.status_code == 200
    names = [c["name"] for c in resp.json()["data"]]
    assert names == ["둘째", "첫째"]
    assert resp.json()["data"][0]["coverImageUrl"] is not None


@pytest.mark.asyncio
async def test_detail_returns_ordered_items(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    uid = await _seed_user(override_db_and_seed)
    await _seed_spot(override_db_and_seed, "CR-D1")
    await _seed_spot(override_db_and_seed, "CR-D2")
    created = await client.post("/v1/courses", json=_body("CR-D1", "CR-D2"), headers=_auth(uid))
    course_id = created.json()["data"]["id"]

    resp = await client.get(f"/v1/courses/{course_id}", headers=_auth(uid))

    assert resp.status_code == 200
    items = resp.json()["data"]["items"]
    assert [it["contentId"] for it in items] == ["CR-D1", "CR-D2"]
    assert [it["position"] for it in items] == [0, 1]


@pytest.mark.asyncio
async def test_detail_of_other_users_course_is_404(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    owner = await _seed_user(override_db_and_seed)
    other = await _seed_user(override_db_and_seed)
    await _seed_spot(override_db_and_seed, "CR-OWN")
    created = await client.post("/v1/courses", json=_body("CR-OWN"), headers=_auth(owner))
    course_id = created.json()["data"]["id"]

    resp = await client.get(f"/v1/courses/{course_id}", headers=_auth(other))

    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


@pytest.mark.asyncio
async def test_delete_removes_my_course(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    uid = await _seed_user(override_db_and_seed)
    await _seed_spot(override_db_and_seed, "CR-DEL")
    created = await client.post("/v1/courses", json=_body("CR-DEL"), headers=_auth(uid))
    course_id = created.json()["data"]["id"]

    deleted = await client.delete(f"/v1/courses/{course_id}", headers=_auth(uid))
    assert deleted.status_code == 204

    after = await client.get(f"/v1/courses/{course_id}", headers=_auth(uid))
    assert after.status_code == 404


@pytest.mark.asyncio
async def test_delete_other_users_course_is_404(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    owner = await _seed_user(override_db_and_seed)
    other = await _seed_user(override_db_and_seed)
    await _seed_spot(override_db_and_seed, "CR-DEL2")
    created = await client.post("/v1/courses", json=_body("CR-DEL2"), headers=_auth(owner))
    course_id = created.json()["data"]["id"]

    resp = await client.delete(f"/v1/courses/{course_id}", headers=_auth(other))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_without_auth_is_401(client: AsyncClient) -> None:
    resp = await client.post("/v1/courses", json=_body("X"))
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_without_auth_is_401(client: AsyncClient) -> None:
    resp = await client.get("/v1/courses")
    assert resp.status_code == 401
