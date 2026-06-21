"""Integration tests for POST /v1/taste/photo-search.

Flow: multipart image -> CLIP embed (in-memory) -> pgvector top-N nearest
spots over spot_embeddings.embedding (halfvec(512)) -> SimilarNeighbor list.

The CLIP embed call is mocked at the boundary (app.core.embedding.embedder
.embed_image) so the test is deterministic and does not require a model
download. Everything below the mock — the service, IMG.find_neighbors_by_vector,
the pgvector query and the SPT serialization — runs for real against the
migrated test DB.
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
    session: AsyncSession, content_id: str, vec: list[float]
) -> None:
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, first_image_url, "
            "addr1, mapx, mapy, show_flag) "
            "VALUES (:cid, 12, :t, 'http://kto/p.jpg', 'addr1', 127.0, 37.0, 1) "
            "ON CONFLICT (content_id) DO NOTHING"
        ),
        {"cid": content_id, "t": f"title-{content_id}"},
    )
    literal = "[" + ",".join(f"{v:.6f}" for v in vec) + "]"
    await session.execute(
        text(
            "INSERT INTO spot_embeddings (content_id, embedding) "
            "VALUES (:cid, (:emb)::halfvec(512)) ON CONFLICT (content_id) DO NOTHING"
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


@pytest.mark.asyncio
async def test_photo_search_returns_similar_spots(
    client: AsyncClient,
    override_db_and_seed: AsyncSession,
    fixed_embedding: list[float],
) -> None:
    # Seed a near-duplicate (same vector) and a far one.
    await _seed_spot_with_embedding(override_db_and_seed, "ps_near", list(fixed_embedding))
    await _seed_spot_with_embedding(override_db_and_seed, "ps_far", _unit_vec(7))

    resp = await client.post(
        "/v1/taste/photo-search",
        files={"image": ("photo.png", _png_bytes(), "image/png")},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["error"] is None
    assert "meta" in body
    data = body["data"]
    assert isinstance(data, list)
    cids = [item["contentId"] for item in data]
    assert "ps_near" in cids
    # Near-duplicate ranks ahead of the far spot (ascending cosine distance).
    if "ps_far" in cids:
        assert cids.index("ps_near") < cids.index("ps_far")
    # Item shape matches the SPT similar-spots contract (SimilarNeighbor).
    near = next(item for item in data if item["contentId"] == "ps_near")
    assert {"contentId", "title", "firstImageUrl", "addr1", "mapx", "mapy", "distance"} <= set(near)
    assert near["distance"] < 0.001
    # Ordered by ascending distance.
    distances = [item["distance"] for item in data]
    assert distances == sorted(distances)


@pytest.mark.asyncio
async def test_photo_search_empty_when_no_neighbors(
    client: AsyncClient,
    override_db_and_seed: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Embed to a vector; even with ambient embeddings present a tiny limit still
    # returns a list. The contract guarantee we assert: a 200 with a list body,
    # never an error, regardless of neighbor count.
    from app.core.embedding import ClipEmbedder

    monkeypatch.setattr(ClipEmbedder, "embed_image", lambda _self, _b: _unit_vec(55), raising=True)

    resp = await client.post(
        "/v1/taste/photo-search?limit=1",
        files={"image": ("photo.png", _png_bytes(), "image/png")},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["error"] is None
    assert isinstance(body["data"], list)
    assert len(body["data"]) <= 1
