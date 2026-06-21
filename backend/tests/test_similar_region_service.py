"""Region-scoped photo similarity at the service layer (ADR-0014).

Covers IMG.find_neighbor_content_ids(region=...) and the SPT.find_similar_spots
wrapper that validates the region code and forwards it. Uses identical unit
vectors so cosine distance is ~0 for every seeded neighbor — region membership
is then the only thing that decides inclusion.
"""

from __future__ import annotations

import math
import random

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationFailed
from app.modules.images.services import find_neighbor_content_ids
from app.modules.spots.services import find_similar_spots


def _unit_vec(seed: int, dim: int = 512) -> list[float]:
    rng = random.Random(seed)
    raw = [rng.gauss(0, 1) for _ in range(dim)]
    norm = math.sqrt(sum(x * x for x in raw))
    return [x / norm for x in raw]


async def _seed(session: AsyncSession, content_id: str, region_cd: str, vec: list[float]) -> None:
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, first_image_url, "
            "show_flag, ldong_regn_cd) "
            "VALUES (:cid, 12, :t, 'http://kto.example/i.jpg', 1, :rc)"
        ),
        {"cid": content_id, "t": f"title-{content_id}", "rc": region_cd},
    )
    literal = "[" + ",".join(f"{v:.6f}" for v in vec) + "]"
    await session.execute(
        text(
            "INSERT INTO spot_embeddings (content_id, embedding) "
            "VALUES (:cid, (:emb)::halfvec(512))"
        ),
        {"cid": content_id, "emb": literal},
    )


@pytest.mark.asyncio
async def test_neighbor_search_restricts_to_region(db_session: AsyncSession) -> None:
    base = _unit_vec(1)
    await _seed(db_session, "srq_q", "51", base)
    await _seed(db_session, "srq_gangwon", "51", base)
    await _seed(db_session, "srq_jeju", "50", base)

    rows = await find_neighbor_content_ids(db_session, "srq_q", limit=30, region="51")
    cids = {cid for cid, _ in rows}
    assert "srq_gangwon" in cids
    assert "srq_jeju" not in cids
    assert "srq_q" not in cids


@pytest.mark.asyncio
async def test_neighbor_search_no_region_spans_regions(db_session: AsyncSession) -> None:
    base = _unit_vec(2)
    await _seed(db_session, "srn_q", "51", base)
    await _seed(db_session, "srn_gangwon", "51", base)
    await _seed(db_session, "srn_jeju", "50", base)

    rows = await find_neighbor_content_ids(db_session, "srn_q", limit=30)
    cids = {cid for cid, _ in rows}
    assert {"srn_gangwon", "srn_jeju"}.issubset(cids)


@pytest.mark.asyncio
async def test_find_similar_unknown_region_raises(db_session: AsyncSession) -> None:
    await _seed(db_session, "sru_q", "51", _unit_vec(3))
    with pytest.raises(ValidationFailed):
        await find_similar_spots(db_session, "sru_q", limit=10, region="99")


@pytest.mark.asyncio
async def test_find_similar_scopes_neighbors_to_region(db_session: AsyncSession) -> None:
    base = _unit_vec(4)
    await _seed(db_session, "srs_q", "51", base)
    await _seed(db_session, "srs_gangwon", "51", base)
    await _seed(db_session, "srs_jeju", "50", base)

    result = await find_similar_spots(db_session, "srs_q", limit=30, region="51")
    cids = {row.content_id for row, _ in result.neighbors}
    assert "srs_gangwon" in cids
    assert "srs_jeju" not in cids
