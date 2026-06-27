"""Admin curation editor — ADM-012~016 / ADM-018 (Phase 4, A01 §7).

The admin module's first *write* surface (scoped to ``curations`` /
``curation_spots`` only). Covers the five editor endpoints under
``/admin/api/*`` (outside ``/v1``, each behind HTTP Basic ``AdminAuth``):

- ``GET    /admin/api/curations``            — list grouped heroes/rails/editorial
- ``GET    /admin/api/curations/{id}``       — detail (copy + cover + handpicks)
- ``PUT    /admin/api/curations/{id}``       — edit copy/cover/publish/position
- ``PUT    /admin/api/curations/{id}/spots`` — replace handpicks (≤8, ordered)
- ``GET    /admin/api/spots/search``         — admin-only spot picker

Plus on-publish cache invalidation (``curation:{id}:spots`` DEL) and the auth
gate. Reuses the seed helpers shape from ``test_home_feed.py`` /
``test_curation_detail.py``.
"""

from __future__ import annotations

from base64 import b64encode

import pytest
from fakeredis.aioredis import FakeRedis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.redis import get_redis
from app.main import app

# DB-backed admin auth: migration 0016 seeds admin/admin into the test DB
# (alembic upgrade head runs before pytest in CI).
_AUTH = {"Authorization": "Basic " + b64encode(b"admin:admin").decode()}


# --- seed helpers (replicated from test_home_feed.py) -------------------------
async def _seed_region(session: AsyncSession, code: str, name: str) -> None:
    await session.execute(
        text(
            "INSERT INTO regions (ldong_regn_cd, ldong_regn_nm) VALUES (:c, :n) "
            "ON CONFLICT DO NOTHING"
        ),
        {"c": code, "n": name},
    )


async def _seed_mood(session: AsyncSession, mid: int, code: str) -> None:
    await session.execute(
        text(
            "INSERT INTO moods (id, code, name, emoji, sort_order) "
            "VALUES (:id, :code, :name, :emoji, :so) ON CONFLICT DO NOTHING"
        ),
        {"id": mid, "code": code, "name": code, "emoji": "x", "so": mid},
    )


async def _seed_spot(
    session: AsyncSession,
    cid: str,
    *,
    region_cd: str | None = None,
    img: str | None = "http://kto/i.jpg",
    show: int = 1,
    title: str | None = None,
    addr1: str | None = None,
) -> None:
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, addr1, first_image_url, "
            "show_flag, ldong_regn_cd) VALUES (:cid, 12, :t, :addr, :img, :show, :rc)"
        ),
        {
            "cid": cid,
            "t": title or f"t-{cid}",
            "addr": addr1,
            "img": img,
            "show": show,
            "rc": region_cd,
        },
    )


async def _seed_curation(
    session: AsyncSession,
    cid: int,
    *,
    type_: str,
    slug: str,
    title: str,
    position: int,
    region_cd: str | None = None,
    mood_id: int | None = None,
    cover_spot_id: str | None = None,
    subtitle: str | None = None,
    lead: str | None = None,
    intro: str | None = None,
    published: bool = True,
) -> None:
    await session.execute(
        text(
            "INSERT INTO curations (id, type, slug, title, subtitle, lead, intro, region_cd, "
            "mood_id, cover_spot_id, is_published, position) "
            "VALUES (:id, :ty, :slug, :title, :sub, :lead, :intro, :rc, :mid, :cov, :pub, :pos)"
        ),
        {
            "id": cid,
            "ty": type_,
            "slug": slug,
            "title": title,
            "sub": subtitle if subtitle is not None else f"sub-{slug}",
            "lead": lead,
            "intro": intro,
            "rc": region_cd,
            "mid": mood_id,
            "cov": cover_spot_id,
            "pub": published,
            "pos": position,
        },
    )


async def _add_handpick(session: AsyncSession, curation_id: int, cid: str, pos: int) -> None:
    await session.execute(
        text("INSERT INTO curation_spots (curation_id, content_id, position) VALUES (:c, :s, :p)"),
        {"c": curation_id, "s": cid, "p": pos},
    )


@pytest.fixture
async def seed(db_session: AsyncSession) -> FakeRedis:
    """Two region heroes, one mood rail, one editorial + handpicks + spots."""
    await _seed_region(db_session, "R0", "region-0")
    await _seed_region(db_session, "R1", "region-1")
    await _seed_mood(db_session, 10, "mood0")

    # cover spot (exposable, image) + a no-image spot + a hidden spot
    await _seed_spot(db_session, "cover-1", region_cd="R0", img="http://kto/cover.jpg")
    await _seed_spot(db_session, "noimg-1", region_cd="R0", img=None)
    await _seed_spot(db_session, "hidden-1", region_cd="R0", show=0)
    for i in range(10):
        await _seed_spot(db_session, f"sp-{i}", region_cd="R0")

    # hero 700 (region, published, has cover), hero 701 (region, unpublished)
    await _seed_curation(
        db_session,
        700,
        type_="region",
        slug="hero-a",
        title="Hero\nA",
        position=0,
        region_cd="R0",
        cover_spot_id="cover-1",
        lead="lead-a",
        intro="intro-a",
    )
    await _seed_curation(
        db_session,
        701,
        type_="region",
        slug="hero-b",
        title="Hero B",
        position=1,
        region_cd="R1",
        published=False,
    )
    # rail 800 (mood, published)
    await _seed_curation(
        db_session, 800, type_="mood", slug="rail-a", title="Rail A", position=0, mood_id=10
    )
    # editorial 900 (published)
    await _seed_curation(
        db_session, 900, type_="editorial", slug="ed-a", title="Editorial A", position=0
    )

    # handpicks for hero 700: sp-2, sp-0, sp-1 in that order
    await _add_handpick(db_session, 700, "sp-2", 0)
    await _add_handpick(db_session, 700, "sp-0", 1)
    await _add_handpick(db_session, 700, "sp-1", 2)
    await db_session.flush()

    return FakeRedis(decode_responses=True)


def _override(db_session: AsyncSession, redis: FakeRedis) -> None:
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_redis] = lambda: redis


# --- ADM-012: list -----------------------------------------------------------
async def test_list_groups_and_resolves_cover(db_session, client, seed) -> None:
    _override(db_session, seed)
    try:
        r = await client.get("/admin/api/curations", headers=_AUTH)
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    data = r.json()["data"]
    heroes = data["heroes"]
    rails = data["rails"]
    editorial = data["editorial"]

    assert [h["id"] for h in heroes] == [700, 701]  # ordered by position
    assert all(h["type"] == "region" for h in heroes)
    assert [c["id"] for c in rails] == [800]
    assert [c["id"] for c in editorial] == [900]

    a = heroes[0]
    assert a["slug"] == "hero-a"
    assert a["title"] == "Hero\nA"  # newline preserved
    assert a["coverUrl"] == "http://kto/cover.jpg"
    assert a["isPublished"] is True
    assert heroes[1]["isPublished"] is False
    assert heroes[1]["coverUrl"] is None  # no cover_spot_id


# --- ADM-012: detail ---------------------------------------------------------
async def test_detail_shape_and_handpicks(db_session, client, seed) -> None:
    _override(db_session, seed)
    try:
        r = await client.get("/admin/api/curations/700", headers=_AUTH)
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    data = r.json()["data"]
    assert data["id"] == 700
    assert data["type"] == "region"
    assert data["slug"] == "hero-a"
    assert data["title"] == "Hero\nA"
    assert data["lead"] == "lead-a"
    assert data["intro"] == "intro-a"
    assert data["regionCd"] == "R0"
    assert data["moodId"] is None
    assert data["isPublished"] is True
    assert data["position"] == 0
    assert data["coverSpot"] == {
        "contentId": "cover-1",
        "name": "t-cover-1",
        "imageUrl": "http://kto/cover.jpg",
    }
    # handpicks ordered by position
    assert [h["contentId"] for h in data["handpicks"]] == ["sp-2", "sp-0", "sp-1"]
    assert [h["position"] for h in data["handpicks"]] == [0, 1, 2]
    assert all(
        {"contentId", "name", "category", "imageUrl", "position"} == h.keys()
        for h in data["handpicks"]
    )


async def test_detail_missing_404(db_session, client, seed) -> None:
    _override(db_session, seed)
    try:
        r = await client.get("/admin/api/curations/99999", headers=_AUTH)
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "ADMIN_CURATION_NOT_FOUND"


# --- ADM-013: update ---------------------------------------------------------
async def test_update_happy_path(db_session, client, seed) -> None:
    _override(db_session, seed)
    body = {
        "title": "New\nTitle",
        "subtitle": "new-sub",
        "lead": "new-lead",
        "intro": "new-intro",
        "coverSpotId": "cover-1",
        "isPublished": False,
        "position": 3,
    }
    try:
        before = (
            await db_session.execute(text("SELECT updated_at FROM curations WHERE id = 700"))
        ).scalar_one()
        r = await client.put("/admin/api/curations/700", json=body, headers=_AUTH)
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    data = r.json()["data"]
    assert data["title"] == "New\nTitle"
    assert data["subtitle"] == "new-sub"
    assert data["lead"] == "new-lead"
    assert data["intro"] == "new-intro"
    assert data["isPublished"] is False
    assert data["position"] == 3
    assert data["coverSpot"]["contentId"] == "cover-1"

    after = (
        await db_session.execute(text("SELECT updated_at FROM curations WHERE id = 700"))
    ).scalar_one()
    assert after >= before


async def test_update_clears_cover(db_session, client, seed) -> None:
    _override(db_session, seed)
    body = {
        "title": "T",
        "subtitle": None,
        "lead": None,
        "intro": None,
        "coverSpotId": None,
        "isPublished": True,
        "position": 0,
    }
    try:
        r = await client.put("/admin/api/curations/700", json=body, headers=_AUTH)
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    assert r.json()["data"]["coverSpot"] is None


@pytest.mark.parametrize(
    ("override", "cover"),
    [
        ({"title": "   "}, "cover-1"),  # blank after strip
        ({"position": -1}, "cover-1"),  # negative position
        ({}, "missing-x"),  # nonexistent cover
        ({}, "noimg-1"),  # exposable but no image
        ({}, "hidden-1"),  # has image but not exposable
    ],
)
async def test_update_validation_422(db_session, client, seed, override, cover) -> None:
    _override(db_session, seed)
    body = {
        "title": "ok-title",
        "subtitle": None,
        "lead": None,
        "intro": None,
        "coverSpotId": cover,
        "isPublished": True,
        "position": 0,
    }
    body.update(override)
    try:
        r = await client.put("/admin/api/curations/700", json=body, headers=_AUTH)
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "ADMIN_VALIDATION"
    assert r.json()["error"]["details"]  # field-level details present


async def test_update_missing_404(db_session, client, seed) -> None:
    _override(db_session, seed)
    body = {
        "title": "t",
        "subtitle": None,
        "lead": None,
        "intro": None,
        "coverSpotId": None,
        "isPublished": True,
        "position": 0,
    }
    try:
        r = await client.put("/admin/api/curations/99999", json=body, headers=_AUTH)
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "ADMIN_CURATION_NOT_FOUND"


# --- ADM-014: spots set ------------------------------------------------------
async def test_spots_replace_ordered_by_index(db_session, client, seed) -> None:
    _override(db_session, seed)
    body = {"spotIds": ["sp-5", "sp-3", "sp-9"]}
    before_updated_at = (
        await db_session.execute(text("SELECT updated_at FROM curations WHERE id = 700"))
    ).scalar_one()
    try:
        r = await client.put("/admin/api/curations/700/spots", json=body, headers=_AUTH)
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    hp = r.json()["data"]["handpicks"]
    assert [h["contentId"] for h in hp] == ["sp-5", "sp-3", "sp-9"]
    assert [h["position"] for h in hp] == [0, 1, 2]
    # DB reflects replacement (old sp-2/sp-0/sp-1 gone)
    rows = (
        (
            await db_session.execute(
                text(
                    "SELECT content_id FROM curation_spots WHERE curation_id = 700 ORDER BY position"
                )
            )
        )
        .scalars()
        .all()
    )
    assert list(rows) == ["sp-5", "sp-3", "sp-9"]
    # FIX 3: parent curations.updated_at must advance after a spots replacement
    after_updated_at = (
        await db_session.execute(text("SELECT updated_at FROM curations WHERE id = 700"))
    ).scalar_one()
    assert after_updated_at > before_updated_at


async def test_spots_empty_clears(db_session, client, seed) -> None:
    _override(db_session, seed)
    try:
        r = await client.put("/admin/api/curations/700/spots", json={"spotIds": []}, headers=_AUTH)
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    assert r.json()["data"]["handpicks"] == []
    count = (
        await db_session.execute(
            text("SELECT count(*) FROM curation_spots WHERE curation_id = 700")
        )
    ).scalar_one()
    assert count == 0


@pytest.mark.parametrize(
    "spot_ids",
    [
        [f"sp-{i}" for i in range(9)],  # > 8
        ["sp-0", "sp-0"],  # duplicate
        ["sp-0", "missing-x"],  # nonexistent
    ],
)
async def test_spots_validation_422(db_session, client, seed, spot_ids) -> None:
    _override(db_session, seed)
    try:
        r = await client.put(
            "/admin/api/curations/700/spots", json={"spotIds": spot_ids}, headers=_AUTH
        )
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "ADMIN_VALIDATION"


async def test_spots_missing_curation_404(db_session, client, seed) -> None:
    _override(db_session, seed)
    try:
        r = await client.put(
            "/admin/api/curations/99999/spots", json={"spotIds": ["sp-0"]}, headers=_AUTH
        )
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "ADMIN_CURATION_NOT_FOUND"


# --- ADM-016: cache invalidation ---------------------------------------------
async def test_publish_put_invalidates_cache(db_session, client, seed) -> None:
    _override(db_session, seed)
    await seed.set("curation:700:spots", "sp-2,sp-0,sp-1")
    body = {
        "title": "t",
        "subtitle": None,
        "lead": None,
        "intro": None,
        "coverSpotId": None,
        "isPublished": True,
        "position": 0,
    }
    try:
        r = await client.put("/admin/api/curations/700", json=body, headers=_AUTH)
        assert r.status_code == 200
        assert await seed.get("curation:700:spots") is None
    finally:
        app.dependency_overrides.clear()


async def test_spots_put_invalidates_cache(db_session, client, seed) -> None:
    _override(db_session, seed)
    await seed.set("curation:700:spots", "sp-2,sp-0,sp-1")
    try:
        r = await client.put(
            "/admin/api/curations/700/spots", json={"spotIds": ["sp-3"]}, headers=_AUTH
        )
        assert r.status_code == 200
        assert await seed.get("curation:700:spots") is None
    finally:
        app.dependency_overrides.clear()


# --- ADM-015: spot search ----------------------------------------------------
async def test_spot_search_matches_title_and_addr(db_session, client, seed) -> None:
    _override(db_session, seed)
    await _seed_spot(
        db_session, "find-me", region_cd="R0", title="Sunny Beach", addr1="123 Coast Rd"
    )
    await _seed_spot(db_session, "by-addr", region_cd="R1", title="Nowhere", addr1="9 Sunny Lane")
    await db_session.flush()
    try:
        r = await client.get("/admin/api/spots/search", params={"q": "sunny"}, headers=_AUTH)
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    spots = r.json()["data"]["spots"]
    ids = {s["contentId"] for s in spots}
    assert "find-me" in ids  # title match
    assert "by-addr" in ids  # addr1 match
    # minimal fields only
    s = next(s for s in spots if s["contentId"] == "find-me")
    assert s.keys() == {"contentId", "name", "regionCd", "regionName", "imageUrl"}
    assert s["name"] == "Sunny Beach"
    assert s["regionCd"] == "R0"
    assert s["regionName"] == "region-0"


async def test_spot_search_region_filter(db_session, client, seed) -> None:
    _override(db_session, seed)
    await _seed_spot(db_session, "r0-hit", region_cd="R0", title="Foobar Park")
    await _seed_spot(db_session, "r1-hit", region_cd="R1", title="Foobar Plaza")
    await db_session.flush()
    try:
        r = await client.get(
            "/admin/api/spots/search", params={"q": "foobar", "region": "R0"}, headers=_AUTH
        )
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    ids = {s["contentId"] for s in r.json()["data"]["spots"]}
    assert "r0-hit" in ids
    assert "r1-hit" not in ids


async def test_spot_search_excludes_hidden(db_session, client, seed) -> None:
    _override(db_session, seed)
    await _seed_spot(db_session, "hid", region_cd="R0", title="Zephyr", show=0)
    await _seed_spot(db_session, "vis", region_cd="R0", title="Zephyr Visible")
    await db_session.flush()
    try:
        r = await client.get("/admin/api/spots/search", params={"q": "zephyr"}, headers=_AUTH)
    finally:
        app.dependency_overrides.clear()
    ids = {s["contentId"] for s in r.json()["data"]["spots"]}
    assert "hid" not in ids
    assert "vis" in ids


# --- ADM-018: auth gate ------------------------------------------------------
@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("GET", "/admin/api/curations", None),
        ("GET", "/admin/api/curations/700", None),
        ("PUT", "/admin/api/curations/700", {"title": "x", "isPublished": True, "position": 0}),
        ("PUT", "/admin/api/curations/700/spots", {"spotIds": []}),
        ("GET", "/admin/api/spots/search?q=a", None),
    ],
)
async def test_auth_required(db_session, client, seed, method, path, body) -> None:
    _override(db_session, seed)
    try:
        r = await client.request(method, path, json=body)
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "ADMIN_UNAUTHORIZED"
