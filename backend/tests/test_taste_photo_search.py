"""Integration tests for POST /v1/taste/photo-search.

CLIP embed is stubbed at the ClipEmbedder.embed_image boundary (deterministic, no model
download); everything below the stub runs for real against the migrated test DB.
"""

from __future__ import annotations

import io
import math
import random
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.main import app


def _unit_vec(seed: int, dim: int = 512) -> list[float]:
    rng = random.Random(seed)
    raw = [rng.gauss(0, 1) for _ in range(dim)]
    norm = math.sqrt(sum(x * x for x in raw))
    return [x / norm for x in raw]


def _png_bytes() -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (8, 8), (123, 200, 50)).save(buf, format="PNG")
    return buf.getvalue()


@pytest_asyncio.fixture(autouse=True)
async def override_db_and_seed() -> AsyncIterator[AsyncSession]:
    from app.core.db import get_db

    eng = create_async_engine(str(settings.sqlalchemy_database_url), poolclass=NullPool)
    async with eng.connect() as conn:
        tx = await conn.begin()
        try:
            seed = AsyncSession(
                bind=conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
            )

            async def _override() -> AsyncIterator[AsyncSession]:
                session = AsyncSession(
                    bind=conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
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


async def _seed_spot_with_embedding(
    session: AsyncSession,
    content_id: str,
    vec: list[float],
    *,
    mapx: float = 127.0,
    mapy: float = 37.0,
) -> None:
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, first_image_url, "
            "addr1, mapx, mapy, show_flag) "
            "VALUES (:cid, 12, :t, 'http://kto/p.jpg', 'addr1', :mapx, :mapy, 1) "
            "ON CONFLICT (content_id) DO NOTHING"
        ),
        {"cid": content_id, "t": f"title-{content_id}", "mapx": mapx, "mapy": mapy},
    )
    literal = "[" + ",".join(f"{v:.6f}" for v in vec) + "]"
    await session.execute(
        text(
            "INSERT INTO spot_embeddings (content_id, embedding) "
            "VALUES (:cid, CAST(:emb AS halfvec(512))) ON CONFLICT (content_id) DO NOTHING"
        ),
        {"cid": content_id, "emb": literal},
    )
    await session.commit()


@pytest.fixture
def fixed_embedding(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Patch the CLIP embed boundary to return a fixed 512-vector."""
    vec = _unit_vec(909)

    def _fake_embed_image(_self: object, image_bytes: bytes) -> list[float]:
        assert image_bytes, "route must forward the uploaded bytes to the embedder"
        return list(vec)

    from app.core.embedding import ClipEmbedder

    monkeypatch.setattr(ClipEmbedder, "embed_image", _fake_embed_image)
    return vec


async def test_photo_search_no_location_returns_matches(
    client: AsyncClient,
    override_db_and_seed: AsyncSession,
    fixed_embedding: list[float],
) -> None:
    # An exact match (similarity ~1.0) clears any floor.
    await _seed_spot_with_embedding(override_db_and_seed, "ps_near", list(fixed_embedding))

    resp = await client.post(
        "/v1/taste/photo-search",
        files={"image": ("photo.png", _png_bytes(), "image/png")},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["error"] is None
    assert "meta" in body
    data = body["data"]
    assert data["queryHadLocation"] is False
    matches = data["matches"]
    assert isinstance(matches, list)
    cids = [m["contentId"] for m in matches]
    assert "ps_near" in cids
    near = next(m for m in matches if m["contentId"] == "ps_near")
    # Card shape + similarity; distance absent without lat/lng.
    assert {"contentId", "title", "firstImageUrl", "similarity"} <= set(near)
    assert near["similarity"] > 0.99
    assert near.get("distance") is None
    # Sorted by similarity desc.
    sims = [m["similarity"] for m in matches]
    assert sims == sorted(sims, reverse=True)


async def test_photo_search_with_location_includes_distance(
    client: AsyncClient,
    override_db_and_seed: AsyncSession,
    fixed_embedding: list[float],
) -> None:
    await _seed_spot_with_embedding(
        override_db_and_seed, "ps_near", list(fixed_embedding), mapx=127.0, mapy=37.0
    )

    resp = await client.post(
        "/v1/taste/photo-search",
        params={"lat": 37.0, "lng": 127.0},
        files={"image": ("photo.png", _png_bytes(), "image/png")},
    )

    assert resp.status_code == 200
    body = resp.json()
    data = body["data"]
    assert data["queryHadLocation"] is True
    near = next(m for m in data["matches"] if m["contentId"] == "ps_near")
    assert "distance" in near
    assert isinstance(near["distance"], int | float)
    # Query point == spot coords → near-zero distance.
    assert near["distance"] < 50.0


async def test_photo_search_below_floor_returns_empty(
    client: AsyncClient,
    override_db_and_seed: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Stub embed to a vector unrelated to seeded embeddings → all neighbors are
    # far (similarity < 0.75 hard cut). No fallback: the result must be empty,
    # not a top-N of the best-available-but-still-poor matches.
    from app.core.embedding import ClipEmbedder

    monkeypatch.setattr(ClipEmbedder, "embed_image", lambda _self, _b: _unit_vec(31), raising=True)
    await _seed_spot_with_embedding(override_db_and_seed, "ps_a", _unit_vec(7))
    await _seed_spot_with_embedding(override_db_and_seed, "ps_b", _unit_vec(8))

    resp = await client.post(
        "/v1/taste/photo-search",
        files={"image": ("photo.png", _png_bytes(), "image/png")},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["error"] is None
    assert body["data"]["matches"] == []


async def test_photo_search_filters_out_matches_below_floor(
    client: AsyncClient,
    override_db_and_seed: AsyncSession,
    fixed_embedding: list[float],
) -> None:
    # One spot near-exactly matches the query (similarity ~1.0, clears 0.75);
    # one spot is unrelated (similarity near 0, well below 0.75). Only the
    # first should come back — the hard filter drops the second outright.
    await _seed_spot_with_embedding(override_db_and_seed, "ps_hit", list(fixed_embedding))
    await _seed_spot_with_embedding(override_db_and_seed, "ps_miss", _unit_vec(42))

    resp = await client.post(
        "/v1/taste/photo-search",
        files={"image": ("photo.png", _png_bytes(), "image/png")},
    )

    assert resp.status_code == 200
    body = resp.json()
    cids = [m["contentId"] for m in body["data"]["matches"]]
    assert "ps_hit" in cids
    assert "ps_miss" not in cids
    assert all(
        m["similarity"] >= settings.PHOTO_SEARCH_SIMILARITY_FLOOR for m in body["data"]["matches"]
    )
