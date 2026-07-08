"""GET /v1/home/feed — backend-assembled feed (6 region heroes + 3 mood rails)."""

from __future__ import annotations

import pytest
from fakeredis.aioredis import FakeRedis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.redis import get_redis
from app.main import app
from app.modules.spots.services import curations as curation_svc


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
    overview: str | None = None,
    embedding: bool = False,
    mood_id: int | None = None,
) -> None:
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, first_image_url, "
            "show_flag, ldong_regn_cd) VALUES (:cid, 12, :t, :img, :show, :rc)"
        ),
        {"cid": cid, "t": f"t-{cid}", "img": img, "show": show, "rc": region_cd},
    )
    if overview is not None:
        await session.execute(
            text(
                "INSERT INTO spot_details (content_id, content_type_id, overview) "
                "VALUES (:cid, 12, :ov)"
            ),
            {"cid": cid, "ov": overview},
        )
    if embedding:
        await session.execute(
            text(
                "INSERT INTO spot_embeddings (content_id, embedding) "
                "VALUES (:cid, CAST(:emb AS halfvec(512)))"
            ),
            {"cid": cid, "emb": "[" + ",".join(["0.1"] * 512) + "]"},
        )
    if mood_id is not None:
        await session.execute(
            text(
                "INSERT INTO spot_moods (content_id, mood_id, confidence, source) "
                "VALUES (:cid, :mid, 1.0, 'manual')"
            ),
            {"cid": cid, "mid": mood_id},
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
    published: bool = True,
) -> None:
    await session.execute(
        text(
            "INSERT INTO curations (id, type, slug, title, subtitle, region_cd, mood_id, "
            "cover_spot_id, is_published, position) "
            "VALUES (:id, :ty, :slug, :title, :sub, :rc, :mid, :cov, :pub, :pos)"
        ),
        {
            "id": cid,
            "ty": type_,
            "slug": slug,
            "title": title,
            "sub": f"sub-{slug}",
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
async def seed_feed(db_session: AsyncSession) -> None:
    """6 published region curations + 3 published mood curations + spots."""
    for i in range(6):
        await _seed_region(db_session, f"R{i}", f"region-{i}")
    for i in range(3):
        await _seed_mood(db_session, 10 + i, f"mood{i}")

    for ri in range(6):
        for si in range(5):
            await _seed_spot(
                db_session,
                f"sp-R{ri}-{si}",
                region_cd=f"R{ri}",
                overview="ov" if si % 2 == 0 else None,
                embedding=si % 3 == 0,
            )
    for mi in range(3):
        for si in range(5):
            await _seed_spot(
                db_session,
                f"sp-M{mi}-{si}",
                region_cd="R0",
                mood_id=10 + mi,
                overview="ov" if si % 2 == 0 else None,
            )

    for i in range(6):
        await _seed_curation(
            db_session,
            100 + i,
            type_="region",
            slug=f"region-{i}",
            title=f"Region\n{i}",
            position=i,
            region_cd=f"R{i}",
        )
    for i in range(3):
        await _seed_curation(
            db_session,
            200 + i,
            type_="mood",
            slug=f"mood-{i}",
            title=f"Mood {i}",
            position=i,
            mood_id=10 + i,
        )
    await db_session.flush()


def _override(db_session: AsyncSession, redis: FakeRedis) -> None:
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_redis] = lambda: redis


async def test_home_feed_shape(db_session, client, seed_feed) -> None:
    redis = FakeRedis(decode_responses=True)
    _override(db_session, redis)
    try:
        r = await client.get("/v1/home/feed")
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data["heroes"]) == 6
    assert len(data["rails"]) == 3
    assert all({"id", "slug", "title", "subtitle", "coverUrl"} <= h.keys() for h in data["heroes"])
    assert all(len(rail["spots"]) <= 8 for rail in data["rails"])


async def test_heroes_ordered_by_position_and_keep_newline(db_session, client, seed_feed) -> None:
    redis = FakeRedis(decode_responses=True)
    _override(db_session, redis)
    try:
        r = await client.get("/v1/home/feed")
    finally:
        app.dependency_overrides.clear()
    heroes = r.json()["data"]["heroes"]
    assert [h["id"] for h in heroes] == [100, 101, 102, 103, 104, 105]
    assert heroes[0]["title"] == "Region\n0"  # \n preserved verbatim


async def test_handpicked_spots_take_precedence(db_session, seed_feed) -> None:
    redis = FakeRedis(decode_responses=True)
    # mood curation 200 gets handpicks in a specific order
    await _add_handpick(db_session, 200, "sp-M0-3", 0)
    await _add_handpick(db_session, 200, "sp-M0-1", 1)
    await db_session.flush()

    cur = await curation_svc.load_curation(db_session, 200)
    rows = await curation_svc.resolve_curation_spots(db_session, redis, cur)
    assert [r.content_id for r in rows] == ["sp-M0-3", "sp-M0-1"]


async def test_handpicked_spots_capped_at_eight(db_session, seed_feed) -> None:
    redis = FakeRedis(decode_responses=True)
    # mood curation 201 gets 9 handpicks; only the first 8 by position must show.
    for pos in range(9):
        await _seed_spot(db_session, f"hp-{pos}", region_cd="R0", mood_id=11)
        await _add_handpick(db_session, 201, f"hp-{pos}", pos)
    await db_session.flush()

    cur = await curation_svc.load_curation(db_session, 201)
    rows = await curation_svc.resolve_curation_spots(db_session, redis, cur)
    assert [r.content_id for r in rows] == [f"hp-{pos}" for pos in range(8)]


async def test_pool_is_deterministic_for_same_date(db_session, seed_feed) -> None:
    redis = FakeRedis(decode_responses=True)
    cur = await curation_svc.load_curation(db_session, 100)  # region R0, no handpicks
    first = await curation_svc.resolve_curation_spots(db_session, redis, cur)
    # clear cache so it recomputes; determinism must come from the hash seed, not redis
    await redis.flushall()
    second = await curation_svc.resolve_curation_spots(db_session, redis, cur)
    assert [r.content_id for r in first] == [r.content_id for r in second]
    assert len(first) <= 8
    assert all(r.first_image_url for r in first)


async def test_pool_cached_with_jitter(db_session, seed_feed) -> None:
    redis = FakeRedis(decode_responses=True)
    cur = await curation_svc.load_curation(db_session, 100)
    await curation_svc.resolve_curation_spots(db_session, redis, cur)
    ttl = await redis.ttl("curation:100:spots")
    assert ttl > 0
    # jitter is a stable function of curation_id (0..600)
    assert curation_svc._jitter(100) == 100 % 601


# --- serving-side quality gates (S02:36 / S11 §6) ------------------------------


async def test_hidden_handpick_excluded_on_resolve(db_session, seed_feed) -> None:
    """Cache rebuild must skip handpicks that are hidden or imageless."""
    redis = FakeRedis(decode_responses=True)
    await _add_handpick(db_session, 200, "sp-M0-3", 0)
    await _add_handpick(db_session, 200, "sp-M0-1", 1)
    await db_session.execute(text("UPDATE spots SET show_flag = 0 WHERE content_id = 'sp-M0-3'"))
    await db_session.flush()

    cur = await curation_svc.load_curation(db_session, 200)
    rows = await curation_svc.resolve_curation_spots(db_session, redis, cur)
    assert [r.content_id for r in rows] == ["sp-M0-1"]


async def test_hidden_spot_dropped_even_with_stale_cache(db_session, seed_feed) -> None:
    """A spot hidden after the day-cache was built must not render until midnight."""
    redis = FakeRedis(decode_responses=True)
    await _add_handpick(db_session, 200, "sp-M0-3", 0)
    await _add_handpick(db_session, 200, "sp-M0-1", 1)
    await db_session.flush()

    cur = await curation_svc.load_curation(db_session, 200)
    first = await curation_svc.resolve_curation_spots(db_session, redis, cur)
    assert [r.content_id for r in first] == ["sp-M0-3", "sp-M0-1"]

    # hide sp-M0-3 WITHOUT invalidating the cache (simulates pipeline show_flag flip)
    await db_session.execute(text("UPDATE spots SET show_flag = 0 WHERE content_id = 'sp-M0-3'"))
    await db_session.flush()
    assert await redis.get("curation:200:spots") == "sp-M0-3,sp-M0-1"  # cache still stale

    second = await curation_svc.resolve_curation_spots(db_session, redis, cur)
    assert [r.content_id for r in second] == ["sp-M0-1"]


async def test_hero_without_resolvable_cover_excluded(db_session, client, seed_feed) -> None:
    """A hero whose coverUrl cannot be resolved is dropped (fewer than 6 allowed)."""
    # curation 105 (R5) has no cover_spot_id; strip every R5 spot image so the
    # auto-fill pool is empty and the cover fallback resolves to nothing.
    await db_session.execute(
        text("UPDATE spots SET first_image_url = NULL WHERE content_id LIKE 'sp-R5-%'")
    )
    await db_session.flush()

    redis = FakeRedis(decode_responses=True)
    _override(db_session, redis)
    try:
        r = await client.get("/v1/home/feed")
    finally:
        app.dependency_overrides.clear()
    heroes = r.json()["data"]["heroes"]
    assert [h["id"] for h in heroes] == [100, 101, 102, 103, 104]


async def test_hidden_cover_spot_image_not_served(db_session, client, seed_feed) -> None:
    """A cover spot hidden after being set must not serve its image; the hero
    falls back to the resolved pool's first image (T1 defense chain)."""
    await _seed_spot(db_session, "hidden-cover", region_cd="R0", img="http://kto/hidden.jpg")
    await db_session.execute(
        text("UPDATE curations SET cover_spot_id = 'hidden-cover' WHERE id = 100")
    )
    await db_session.execute(
        text("UPDATE spots SET show_flag = 0 WHERE content_id = 'hidden-cover'")
    )
    await db_session.flush()

    redis = FakeRedis(decode_responses=True)
    _override(db_session, redis)
    try:
        r = await client.get("/v1/home/feed")
    finally:
        app.dependency_overrides.clear()
    hero = next(h for h in r.json()["data"]["heroes"] if h["id"] == 100)
    assert hero["coverUrl"] != "http://kto/hidden.jpg"  # hidden spot never rendered
    assert hero["coverUrl"] == "http://kto/i.jpg"  # pool-first-image fallback


async def test_rail_with_fewer_than_three_spots_omitted(db_session, client, seed_feed) -> None:
    """A mood rail resolving to fewer than 3 spots is omitted from the feed."""
    await db_session.execute(
        text("UPDATE spots SET show_flag = 0 WHERE content_id IN ('sp-M2-0', 'sp-M2-1', 'sp-M2-2')")
    )
    await db_session.flush()

    redis = FakeRedis(decode_responses=True)
    _override(db_session, redis)
    try:
        r = await client.get("/v1/home/feed")
    finally:
        app.dependency_overrides.clear()
    rails = r.json()["data"]["rails"]
    assert [rail["id"] for rail in rails] == [200, 201]


async def test_published_curations_position_tie_broken_by_id(db_session, seed_feed) -> None:
    """Equal positions must sort deterministically by id (matches the admin list)."""
    # Insert in descending-id order so a missing tiebreak (heap/insertion order)
    # would surface as [303, 302, 301].
    for cid in (303, 302, 301):
        await _seed_curation(
            db_session, cid, type_="editorial", slug=f"ed-{cid}", title=f"Ed {cid}", position=7
        )
    await db_session.flush()

    rows = await curation_svc.list_published_curations(db_session, "editorial")
    assert [r.id for r in rows] == [301, 302, 303]
