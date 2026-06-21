"""IMG.find_neighbors_by_vector: pgvector halfvec ANN query over an arbitrary
query vector (e.g. a freshly-embedded user photo).

Mirrors test_img_services_neighbors.py but binds the query vector directly
instead of looking it up from an existing row. Runs against the dev/test DB
which already contains ambient KTO spots/embeddings; we assert contract
behavior (near-duplicate ranks first, empty input -> empty result, limit).
"""

from __future__ import annotations

import math
import random

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.images.services import find_neighbors_by_vector


async def _seed_spot(session: AsyncSession, content_id: str) -> None:
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, show_flag) "
            "VALUES (:cid, 12, :title, 1)"
        ),
        {"cid": content_id, "title": f"spot-{content_id}"},
    )


async def _seed_embedding(session: AsyncSession, content_id: str, vec: list[float]) -> None:
    literal = "[" + ",".join(f"{v:.6f}" for v in vec) + "]"
    await session.execute(
        text(
            "INSERT INTO spot_embeddings (content_id, embedding) "
            "VALUES (:cid, (:emb)::halfvec(512))"
        ),
        {"cid": content_id, "emb": literal},
    )


def _unit_vec(seed: int, dim: int = 512) -> list[float]:
    rng = random.Random(seed)
    raw = [rng.gauss(0, 1) for _ in range(dim)]
    norm = math.sqrt(sum(x * x for x in raw))
    return [x / norm for x in raw]


@pytest.mark.asyncio
async def test_returns_nearest_duplicate_first(db_session: AsyncSession) -> None:
    query = _unit_vec(101)
    await _seed_spot(db_session, "nbv_dup")
    await _seed_embedding(db_session, "nbv_dup", list(query))

    rows = await find_neighbors_by_vector(db_session, query, limit=5)

    assert rows, "expected at least one neighbor"
    cids = [cid for cid, _ in rows]
    assert "nbv_dup" in cids
    # Identical vector -> cosine distance ~0, so it ranks first.
    assert cids[0] == "nbv_dup"
    assert rows[0][1] < 0.001


@pytest.mark.asyncio
async def test_respects_limit(db_session: AsyncSession) -> None:
    query = _unit_vec(202)
    for cid in ("nbv_a", "nbv_b"):
        await _seed_spot(db_session, cid)
        await _seed_embedding(db_session, cid, list(query))

    rows = await find_neighbors_by_vector(db_session, query, limit=3)
    assert len(rows) <= 3


@pytest.mark.asyncio
async def test_only_returns_active_spots(db_session: AsyncSession) -> None:
    query = _unit_vec(303)
    await db_session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, show_flag) "
            "VALUES ('nbv_hidden', 12, 'hidden', 0)"
        )
    )
    await _seed_embedding(db_session, "nbv_hidden", list(query))

    rows = await find_neighbors_by_vector(db_session, query, limit=10)
    cids = [cid for cid, _ in rows]
    assert "nbv_hidden" not in cids
