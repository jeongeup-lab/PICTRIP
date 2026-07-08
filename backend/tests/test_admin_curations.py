"""Admin curation editor — ADM-012~016 / ADM-018 (Phase 4, A01 §7).

The admin module's first *write* surface (scoped to ``curations`` /
``curation_spots`` only). Covers the five editor endpoints under
``/admin/api/*`` (outside ``/v1``, each behind HTTP Basic ``AdminAuth``):

- ``GET    /admin/api/curations``            — list grouped heroes/rails
- ``GET    /admin/api/curations/{id}``       — detail (copy + cover + handpicks)
- ``PUT    /admin/api/curations/positions``  — atomic per-type reorder
- ``PUT    /admin/api/curations/{id}``       — edit copy/cover
- ``PUT    /admin/api/curations/{id}/spots`` — replace handpicks (≤8, ordered)
- ``GET    /admin/api/spots/search``         — admin-only spot picker

Plus on-write cache invalidation (``curation:{id}:spots`` DEL) and the auth
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
from app.modules.admin.security import require_admin

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


async def _seed_sigungu(session: AsyncSession, code: str, region_cd: str, name: str) -> None:
    await session.execute(
        text(
            "INSERT INTO sigungus (ldong_signgu_cd, ldong_regn_cd, ldong_signgu_nm) "
            "VALUES (:c, :r, :n) ON CONFLICT DO NOTHING"
        ),
        {"c": code, "r": region_cd, "n": name},
    )


async def _seed_spot(
    session: AsyncSession,
    cid: str,
    *,
    region_cd: str | None = None,
    sigungu_cd: str | None = None,
    img: str | None = "http://kto/i.jpg",
    show: int = 1,
    title: str | None = None,
    addr1: str | None = None,
    lcls1: str | None = None,
    lcls2: str | None = None,
    lcls3: str | None = None,
) -> None:
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, addr1, first_image_url, "
            "show_flag, ldong_regn_cd, ldong_signgu_cd, lcls_systm1, lcls_systm2, lcls_systm3) "
            "VALUES (:cid, 12, :t, :addr, :img, :show, :rc, :sg, :l1, :l2, :l3)"
        ),
        {
            "cid": cid,
            "t": title or f"t-{cid}",
            "addr": addr1,
            "img": img,
            "show": show,
            "rc": region_cd,
            "sg": sigungu_cd,
            "l1": lcls1,
            "l2": lcls2,
            "l3": lcls3,
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
    """Two region heroes, one mood rail, one editorial (ignored) + handpicks + spots."""
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
    # editorial 900 — legacy type; the admin board must ignore it entirely
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
    app.dependency_overrides[require_admin] = lambda: "admin"


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

    # publish concept removed from the admin surface: no isPublished, and the
    # legacy editorial group is gone even though an editorial row (900) exists.
    assert "editorial" not in data
    assert [h["id"] for h in heroes] == [700, 701]  # ordered by position
    assert all(h["type"] == "region" for h in heroes)
    assert all("isPublished" not in h for h in heroes)
    assert [c["id"] for c in rails] == [800]

    a = heroes[0]
    assert a["slug"] == "hero-a"
    assert a["title"] == "Hero\nA"  # newline preserved
    assert a["coverUrl"] == "http://kto/cover.jpg"
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
    assert "isPublished" not in data  # publish concept removed from admin
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


# --- preview (resolved display spots: handpick else auto-fill) ----------------
async def test_preview_resolves_handpicks(db_session, client, seed) -> None:
    _override(db_session, seed)
    try:
        r = await client.get("/admin/api/curations/700/preview", headers=_AUTH)
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    spots = r.json()["data"]["spots"]
    # handpicks resolve in their stored order, hydrated with name/image
    assert [s["contentId"] for s in spots] == ["sp-2", "sp-0", "sp-1"]
    assert all({"contentId", "name", "category", "imageUrl"} == s.keys() for s in spots)
    assert spots[0]["name"] == "t-sp-2"
    assert spots[0]["imageUrl"] == "http://kto/i.jpg"


async def test_preview_missing_404(db_session, client, seed) -> None:
    _override(db_session, seed)
    try:
        r = await client.get("/admin/api/curations/99999/preview", headers=_AUTH)
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
        "position": 3,  # legacy field (a cached old UI may send it) — must be IGNORED
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
    # ordering moved to PUT /admin/api/curations/positions — the legacy position
    # key in the PUT body is ignored, never applied.
    assert data["position"] == 0
    assert data["coverSpot"]["contentId"] == "cover-1"
    pos = (
        await db_session.execute(text("SELECT position FROM curations WHERE id = 700"))
    ).scalar_one()
    assert pos == 0

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
        "position": 0,
    }
    try:
        r = await client.put("/admin/api/curations/700", json=body, headers=_AUTH)
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    assert r.json()["data"]["coverSpot"] is None


async def test_update_ignores_legacy_is_published_field(db_session, client, seed) -> None:
    """A cached copy of the old UI may still send isPublished — the PUT schema
    must ignore it (pydantic extra ignore), and the DB column must stay untouched."""
    _override(db_session, seed)
    body = {
        "title": "still-published",
        "subtitle": None,
        "lead": None,
        "intro": None,
        "coverSpotId": None,
        "isPublished": False,  # legacy extra field — must be ignored, not 422
        "position": 0,
    }
    try:
        r = await client.put("/admin/api/curations/700", json=body, headers=_AUTH)
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    assert "isPublished" not in r.json()["data"]
    published = (
        await db_session.execute(text("SELECT is_published FROM curations WHERE id = 700"))
    ).scalar_one()
    assert published is True  # write path no longer touches is_published


@pytest.mark.parametrize(
    ("override", "cover"),
    [
        ({"title": "   "}, "cover-1"),  # blank after strip
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
        ["sp-0", "hidden-1"],  # exists but show_flag=0
        ["sp-0", "noimg-1"],  # exists but no first_image_url
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


async def test_spots_gate_reports_rejected_content_ids(db_session, client, seed) -> None:
    """Quality gate: rejected contentIds (hidden / imageless) are listed in details."""
    _override(db_session, seed)
    try:
        r = await client.put(
            "/admin/api/curations/700/spots",
            json={"spotIds": ["sp-0", "hidden-1", "noimg-1"]},
            headers=_AUTH,
        )
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 422
    details = r.json()["error"]["details"]
    issues = " ".join(d["issue"] for d in details)
    assert "hidden-1" in issues
    assert "noimg-1" in issues
    assert "sp-0" not in issues  # the exposable spot is not blamed


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


# --- atomic per-type reorder: PUT /admin/api/curations/positions ---------------
async def test_positions_reorders_atomically_and_audits(db_session, client, seed, capsys) -> None:
    _override(db_session, seed)
    before = (
        await db_session.execute(text("SELECT updated_at FROM curations WHERE id = 700"))
    ).scalar_one()
    try:
        r = await client.put(
            "/admin/api/curations/positions",
            json={"type": "region", "orderedIds": [701, 700]},
            headers=_AUTH,
        )
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    data = r.json()["data"]
    # response is the refreshed board — heroes in the new order
    assert [h["id"] for h in data["heroes"]] == [701, 700]
    assert [h["position"] for h in data["heroes"]] == [0, 1]
    assert [c["id"] for c in data["rails"]] == [800]  # other type untouched

    # DB reflects position = array index
    rows = dict(
        (
            await db_session.execute(
                text("SELECT id, position FROM curations WHERE type = 'region'")
            )
        ).all()
    )
    assert rows == {701: 0, 700: 1}
    # untouched types keep their positions
    mood_pos = (
        await db_session.execute(text("SELECT position FROM curations WHERE id = 800"))
    ).scalar_one()
    assert mood_pos == 0
    editorial_pos = (
        await db_session.execute(text("SELECT position FROM curations WHERE id = 900"))
    ).scalar_one()
    assert editorial_pos == 0
    # updated_at bumped on the reordered rows
    after = (
        await db_session.execute(text("SELECT updated_at FROM curations WHERE id = 700"))
    ).scalar_one()
    assert after > before
    # one structured audit line
    out = capsys.readouterr().out
    assert "curation.positions" in out


@pytest.mark.parametrize(
    "body",
    [
        {"type": "editorial", "orderedIds": [900]},  # type not in (region, mood)
        {"type": "banana", "orderedIds": [700, 701]},  # unknown type
        {"type": "region", "orderedIds": [700]},  # partial list
        {"type": "region", "orderedIds": [700, 700, 701]},  # duplicate id
        {"type": "region", "orderedIds": [700, 800]},  # cross-type id mixed in
        {"type": "region", "orderedIds": [700, 701, 99999]},  # unknown id
        {"type": "mood", "orderedIds": [800, 700]},  # region id in a mood reorder
    ],
)
async def test_positions_validation_422(db_session, client, seed, body) -> None:
    _override(db_session, seed)
    try:
        r = await client.put("/admin/api/curations/positions", json=body, headers=_AUTH)
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "ADMIN_VALIDATION"
    assert r.json()["error"]["details"]
    # nothing applied — original order intact
    rows = dict(
        (
            await db_session.execute(
                text("SELECT id, position FROM curations WHERE type = 'region'")
            )
        ).all()
    )
    assert rows == {700: 0, 701: 1}


# --- ADM-016: cache invalidation ---------------------------------------------
async def test_update_put_invalidates_cache(db_session, client, seed) -> None:
    _override(db_session, seed)
    await seed.set("curation:700:spots", "sp-2,sp-0,sp-1")
    body = {
        "title": "t",
        "subtitle": None,
        "lead": None,
        "intro": None,
        "coverSpotId": None,
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


async def test_spot_search_excludes_imageless(db_session, client, seed) -> None:
    """Picker must not surface active-but-imageless spots — the cover/handpick
    save gate would 422 them, so results must match what can actually be saved."""
    _override(db_session, seed)
    await _seed_spot(db_session, "noimg", region_cd="R0", title="Quokka", img=None)
    await _seed_spot(db_session, "empty", region_cd="R0", title="Quokka Empty", img="")
    await _seed_spot(db_session, "ok", region_cd="R0", title="Quokka Ready")
    await db_session.flush()
    try:
        r = await client.get("/admin/api/spots/search", params={"q": "quokka"}, headers=_AUTH)
    finally:
        app.dependency_overrides.clear()
    ids = {s["contentId"] for s in r.json()["data"]["spots"]}
    assert ids == {"ok"}


async def test_spot_search_sigungu_filter(db_session, client, seed) -> None:
    _override(db_session, seed)
    await _seed_sigungu(db_session, "SG1", "R0", "sigungu-1")
    await _seed_sigungu(db_session, "SG2", "R0", "sigungu-2")
    await _seed_spot(db_session, "sg1-hit", region_cd="R0", sigungu_cd="SG1", title="Gungu Park A")
    await _seed_spot(db_session, "sg2-hit", region_cd="R0", sigungu_cd="SG2", title="Gungu Park B")
    await db_session.flush()
    try:
        r = await client.get(
            "/admin/api/spots/search",
            params={"q": "gungu park", "region": "R0", "sigungu": "SG1"},
            headers=_AUTH,
        )
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    ids = {s["contentId"] for s in r.json()["data"]["spots"]}
    assert ids == {"sg1-hit"}


async def test_spot_search_category_filter(db_session, client, seed) -> None:
    """category maps through the NearbyCategory SSOT predicate — incl. the
    FD030100 exception (bakery counts as cafe, not food)."""
    _override(db_session, seed)
    # lcls_systm3 has an FK to lcls_systm_codes — seed the code row first
    await db_session.execute(
        text(
            "INSERT INTO lcls_systm_codes (lcls_systm3_cd, lcls_systm3_nm) "
            "VALUES ('FD030100', '베이커리') ON CONFLICT DO NOTHING"
        )
    )
    await _seed_spot(db_session, "cat-food", region_cd="R0", title="Catty Diner", lcls2="FD01")
    await _seed_spot(db_session, "cat-cafe", region_cd="R0", title="Catty Cafe", lcls2="FD05")
    await _seed_spot(db_session, "cat-attr", region_cd="R0", title="Catty Palace", lcls1="HS")
    await _seed_spot(
        db_session,
        "cat-bakery",
        region_cd="R0",
        title="Catty Bakery",
        lcls2="FD03",
        lcls3="FD030100",
    )
    await db_session.flush()

    async def _search(category: str) -> set[str]:
        r = await client.get(
            "/admin/api/spots/search", params={"q": "catty", "category": category}, headers=_AUTH
        )
        assert r.status_code == 200
        return {s["contentId"] for s in r.json()["data"]["spots"]}

    try:
        assert await _search("food") == {"cat-food"}
        assert await _search("cafe") == {"cat-cafe", "cat-bakery"}
        assert await _search("attraction") == {"cat-attr"}
    finally:
        app.dependency_overrides.clear()


async def test_spot_search_invalid_category_422(db_session, client, seed) -> None:
    _override(db_session, seed)
    try:
        r = await client.get(
            "/admin/api/spots/search", params={"q": "x", "category": "bogus"}, headers=_AUTH
        )
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "ADMIN_VALIDATION"


async def test_spot_search_browse_without_q(db_session, client, seed) -> None:
    """q is optional — region/sigungu/category alone must allow browsing."""
    _override(db_session, seed)
    await _seed_sigungu(db_session, "SG1", "R0", "sigungu-1")
    await _seed_spot(
        db_session, "br-food", region_cd="R0", sigungu_cd="SG1", title="Browse Diner", lcls2="FD01"
    )
    await _seed_spot(
        db_session, "br-attr", region_cd="R0", sigungu_cd="SG1", title="Browse Hall", lcls1="HS"
    )
    await db_session.flush()
    try:
        r = await client.get(
            "/admin/api/spots/search",
            params={"sigungu": "SG1", "category": "food"},
            headers=_AUTH,
        )
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    ids = {s["contentId"] for s in r.json()["data"]["spots"]}
    assert ids == {"br-food"}


async def test_spot_search_offset_pagination_and_total(db_session, client, seed) -> None:
    _override(db_session, seed)
    for i in range(25):
        await _seed_spot(db_session, f"pg-{i:02d}", region_cd="R0", title=f"Paged spot {i:02d}")
    await db_session.flush()
    try:
        page1 = await client.get("/admin/api/spots/search", params={"q": "paged"}, headers=_AUTH)
        page2 = await client.get(
            "/admin/api/spots/search", params={"q": "paged", "offset": 20}, headers=_AUTH
        )
    finally:
        app.dependency_overrides.clear()

    assert page1.status_code == 200
    d1 = page1.json()["data"]
    assert d1["total"] == 25
    assert d1["hasMore"] is True
    # page size stays 20, ordered by title
    assert [s["contentId"] for s in d1["spots"]] == [f"pg-{i:02d}" for i in range(20)]

    d2 = page2.json()["data"]
    assert d2["total"] == 25
    assert d2["hasMore"] is False
    assert [s["contentId"] for s in d2["spots"]] == [f"pg-{i:02d}" for i in range(20, 25)]


async def test_spot_search_escapes_like_wildcards(db_session, client, seed) -> None:
    """% and _ in q are literals, not LIKE wildcards."""
    _override(db_session, seed)
    await _seed_spot(db_session, "pct-lit", region_cd="R0", title="Sale 50% Off")
    await _seed_spot(db_session, "pct-x", region_cd="R0", title="Sale 50x Off")
    await _seed_spot(db_session, "und-lit", region_cd="R0", title="A_B Cafe")
    await _seed_spot(db_session, "und-x", region_cd="R0", title="AxB Cafe")
    await db_session.flush()
    try:
        r_pct = await client.get("/admin/api/spots/search", params={"q": "50%"}, headers=_AUTH)
        r_und = await client.get("/admin/api/spots/search", params={"q": "A_B"}, headers=_AUTH)
    finally:
        app.dependency_overrides.clear()

    assert {s["contentId"] for s in r_pct.json()["data"]["spots"]} == {"pct-lit"}
    assert {s["contentId"] for s in r_und.json()["data"]["spots"]} == {"und-lit"}


# --- ADM-018: auth gate ------------------------------------------------------
@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("GET", "/admin/api/curations", None),
        ("GET", "/admin/api/curations/700", None),
        ("GET", "/admin/api/curations/700/preview", None),
        ("PUT", "/admin/api/curations/700", {"title": "x"}),
        ("PUT", "/admin/api/curations/700/spots", {"spotIds": []}),
        ("PUT", "/admin/api/curations/positions", {"type": "region", "orderedIds": [700, 701]}),
        ("GET", "/admin/api/spots/search?q=a", None),
    ],
)
async def test_auth_required(db_session, client, seed, method, path, body) -> None:
    _override(db_session, seed)
    # Exercise the real session gate (not the test auth override) for this case.
    app.dependency_overrides.pop(require_admin, None)
    try:
        r = await client.request(method, path, json=body)
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "ADMIN_UNAUTHORIZED"


# --- KTO image http->https upgrade (admin HTML CSP blocks http: images) -------
# The admin console serves its HTML with CSP ``img-src 'self' data: https:``,
# so a raw KTO ``http://`` firstimage URL would be blocked and render blank.
# The admin DTOs upgrade the transport for the KTO host (same URL, no download),
# mirroring the map/spots schemas. Pure-schema test — no DB needed.
def test_admin_image_urls_upgrade_kto_http_to_https() -> None:
    from app.modules.admin.schemas import (
        CoverSpot,
        CurationListItem,
        Handpick,
        SpotSearchItem,
    )

    kto = "http://tong.visitkorea.or.kr/cms/126508_image2.jpg"
    https = "https://tong.visitkorea.or.kr/cms/126508_image2.jpg"
    other = "http://example.test/i.jpg"  # non-KTO host: left untouched

    assert (
        CurationListItem(
            id=1,
            type="region",
            slug="jeju",
            title="제주",
            subtitle=None,
            coverUrl=kto,
            position=0,
        ).coverUrl
        == https
    )
    assert CoverSpot(contentId="1", name="n", imageUrl=kto).imageUrl == https
    assert (
        Handpick(contentId="1", name="n", category=None, imageUrl=kto, position=0).imageUrl == https
    )

    search = SpotSearchItem(contentId="1", name="n", regionCd=None, regionName=None, imageUrl=kto)
    assert search.imageUrl == https
    # non-KTO host and None pass through unchanged
    assert (
        SpotSearchItem(
            contentId="1", name="n", regionCd=None, regionName=None, imageUrl=other
        ).imageUrl
        == other
    )
    assert (
        SpotSearchItem(
            contentId="1", name="n", regionCd=None, regionName=None, imageUrl=None
        ).imageUrl
        is None
    )
