"""IMG.find_neighbor_content_ids: pgvector halfvec ANN query.

These tests run against the dev DB which already contains ambient KTO
spots/embeddings. We assert contract behavior (self-exclusion, ordering of
the inserted near-duplicate, empty-on-missing-embedding) rather than
absolute rank against the global vector space.
"""

from __future__ import annotations

import math
import random

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.images.services import find_neighbor_content_ids


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
async def test_excludes_self_and_returns_nearest_duplicate_first(
    db_session: AsyncSession,
) -> None:
    base = _unit_vec(1)
    duplicate = list(base)

    for cid in ("ng_q", "ng_dup"):
        await _seed_spot(db_session, cid)
    await _seed_embedding(db_session, "ng_q", base)
    await _seed_embedding(db_session, "ng_dup", duplicate)

    rows = await find_neighbor_content_ids(db_session, "ng_q", limit=5)

    assert rows, "expected at least one neighbor"
    cids = [cid for cid, _ in rows]
    assert "ng_q" not in cids
    assert cids[0] == "ng_dup"
    assert rows[0][1] < 0.001  # cosine distance for an identical vector


@pytest.mark.asyncio
async def test_returns_empty_when_query_has_no_embedding(
    db_session: AsyncSession,
) -> None:
    await _seed_spot(db_session, "ng_noemb")
    rows = await find_neighbor_content_ids(db_session, "ng_noemb", limit=5)
    assert rows == []


@pytest.mark.asyncio
async def test_respects_limit(db_session: AsyncSession) -> None:
    base = _unit_vec(7)
    for cid in ("ng_q2", "ng_d2"):
        await _seed_spot(db_session, cid)
    await _seed_embedding(db_session, "ng_q2", base)
    await _seed_embedding(db_session, "ng_d2", base)

    rows = await find_neighbor_content_ids(db_session, "ng_q2", limit=3)
    assert len(rows) <= 3
