"""GET /v1/curations/{slug} — region/curation detail (S09 §5.2)."""

from __future__ import annotations

import pytest
from fakeredis.aioredis import FakeRedis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.redis import get_redis
from app.main import app


async def _seed_region(session: AsyncSession, code: str, name: str) -> None:
    await session.execute(
        text(
            "INSERT INTO regions (ldong_regn_cd, ldong_regn_nm) VALUES (:c, :n) "
            "ON CONFLICT DO NOTHING"
        ),
        {"c": code, "n": name},
    )


async def _seed_spot(
    session: AsyncSession,
    cid: str,
    *,
    region_cd: str,
    img: str | None = "http://kto/i.jpg",
) -> None:
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, first_image_url, "
            "show_flag, ldong_regn_cd) VALUES (:cid, 12, :t, :img, 1, :rc)"
        ),
        {"cid": cid, "t": f"t-{cid}", "img": img, "rc": region_cd},
    )


async def _seed_curation(
    session: AsyncSession,
    cid: int,
    *,
    slug: str,
    title: str,
    region_cd: str,
    lead: str | None = None,
    intro: str | None = None,
    cover_spot_id: str | None = None,
    published: bool = True,
) -> None:
    await session.execute(
        text(
            "INSERT INTO curations (id, type, slug, title, subtitle, lead, intro, "
            "region_cd, cover_spot_id, is_published, position) "
            "VALUES (:id, 'region', :slug, :title, :sub, :lead, :intro, :rc, :cov, :pub, 0)"
        ),
        {
            "id": cid,
            "slug": slug,
            "title": title,
            "sub": f"sub-{slug}",
            "lead": lead,
            "intro": intro,
            "rc": region_cd,
            "cov": cover_spot_id,
            "pub": published,
        },
    )


@pytest.fixture
async def seed_detail(db_session: AsyncSession) -> None:
    await _seed_region(db_session, "RX", "region-x")
    for si in range(5):
        await _seed_spot(db_session, f"sp-RX-{si}", region_cd="RX")
    # cover spot has its own image
    await _seed_spot(db_session, "cover-1", region_cd="RX", img="http://kto/cover.jpg")
    await _seed_curation(
        db_session,
        500,
        slug="region-x",
        title="Region\nX",
        region_cd="RX",
        lead="lead text",
        intro="intro text",
        cover_spot_id="cover-1",
    )
    # unpublished curation
    await _seed_curation(
        db_session,
        501,
        slug="hidden",
        title="Hidden",
        region_cd="RX",
        published=False,
    )
    await db_session.flush()


def _override(db_session: AsyncSession, redis: FakeRedis) -> None:
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_redis] = lambda: redis


async def test_curation_detail_shape(db_session, client, seed_detail) -> None:
    redis = FakeRedis(decode_responses=True)
    _override(db_session, redis)
    try:
        r = await client.get("/v1/curations/region-x")
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    data = r.json()["data"]
    assert data["id"] == 500
    assert data["type"] == "region"
    assert data["slug"] == "region-x"
    assert data["title"] == "Region\nX"  # \n preserved verbatim
    assert data["lead"] == "lead text"
    assert data["intro"] == "intro text"
    # cover spot's image wins the coverUrl fallback
    assert data["coverUrl"] == "http://kto/cover.jpg"
    # subtitle is omitted (S09 §5.2)
    assert "subtitle" not in data
    assert len(data["spots"]) <= 8
    assert all({"contentId", "title", "firstImageUrl"} <= s.keys() for s in data["spots"])


async def test_curation_detail_unknown_slug_404(db_session, client, seed_detail) -> None:
    redis = FakeRedis(decode_responses=True)
    _override(db_session, redis)
    try:
        r = await client.get("/v1/curations/nope")
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 404
    assert r.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


async def test_curation_detail_unpublished_404(db_session, client, seed_detail) -> None:
    redis = FakeRedis(decode_responses=True)
    _override(db_session, redis)
    try:
        r = await client.get("/v1/curations/hidden")
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 404
    assert r.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
