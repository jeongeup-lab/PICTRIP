"""SPT discover services — list_spots_by_mood, find_similar_spots."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ResourceNotFound
from app.modules.spots.services import find_similar_spots, list_spots_by_mood


async def _seed_spot_with_mood(
    session: AsyncSession,
    content_id: str,
    mood_code: str,
    *,
    title: str = "title",
    image_url: str | None = "http://kto.example/img.jpg",
    show_flag: int = 1,
) -> None:
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, first_image_url, show_flag) "
            "VALUES (:cid, 12, :title, :img, :sf)"
        ),
        {"cid": content_id, "title": title, "img": image_url, "sf": show_flag},
    )
    await session.execute(
        text(
            "INSERT INTO spot_moods (content_id, mood_id, confidence, source) "
            "SELECT :cid, id, 1.0, 'manual' FROM moods WHERE code = :code"
        ),
        {"cid": content_id, "code": mood_code},
    )


@pytest.mark.asyncio
async def test_returns_spots_for_mood(db_session: AsyncSession) -> None:
    await _seed_spot_with_mood(db_session, "lsbm_a1", "sea")
    await _seed_spot_with_mood(db_session, "lsbm_a2", "sea")
    await _seed_spot_with_mood(db_session, "lsbm_b1", "mountain")

    rows = await list_spots_by_mood(db_session, "sea", limit=10000)
    cids = {r.content_id for r in rows}
    assert {"lsbm_a1", "lsbm_a2"}.issubset(cids)
    assert "lsbm_b1" not in cids


@pytest.mark.asyncio
async def test_excludes_other_moods(db_session: AsyncSession) -> None:
    """All returned spots must actually belong to the requested mood."""
    await _seed_spot_with_mood(db_session, "lsbm_other_mtn", "mountain")
    await _seed_spot_with_mood(db_session, "lsbm_other_lake", "lake")

    rows = await list_spots_by_mood(db_session, "sea", limit=10000)
    cids = {r.content_id for r in rows}
    assert "lsbm_other_mtn" not in cids
    assert "lsbm_other_lake" not in cids


@pytest.mark.asyncio
async def test_filters_out_inactive_and_imageless(db_session: AsyncSession) -> None:
    await _seed_spot_with_mood(db_session, "lsbm_ok", "sea")
    await _seed_spot_with_mood(db_session, "lsbm_hidden", "sea", show_flag=0)
    await _seed_spot_with_mood(db_session, "lsbm_noimg", "sea", image_url=None)

    rows = await list_spots_by_mood(db_session, "sea", limit=10000)
    cids = {r.content_id for r in rows}
    assert "lsbm_ok" in cids
    assert "lsbm_hidden" not in cids
    assert "lsbm_noimg" not in cids


@pytest.mark.asyncio
async def test_raises_404_for_unknown_mood(db_session: AsyncSession) -> None:
    with pytest.raises(ResourceNotFound):
        await list_spots_by_mood(db_session, "doesnotexist", limit=8)


async def _seed_bare_spot(session: AsyncSession, content_id: str) -> None:
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, first_image_url, show_flag) "
            "VALUES (:cid, 12, :title, 'http://kto.example/i.jpg', 1)"
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
    import math
    import random

    rng = random.Random(seed)
    raw = [rng.gauss(0, 1) for _ in range(dim)]
    norm = math.sqrt(sum(x * x for x in raw))
    return [x / norm for x in raw]


@pytest.mark.asyncio
async def test_find_similar_returns_query_and_neighbors(
    db_session: AsyncSession,
) -> None:
    for cid in ("fss_q", "fss_dup"):
        await _seed_bare_spot(db_session, cid)
    base = _unit_vec(1)
    await _seed_embedding(db_session, "fss_q", base)
    await _seed_embedding(db_session, "fss_dup", base)

    result = await find_similar_spots(db_session, "fss_q", limit=5)

    assert result.query.content_id == "fss_q"
    neighbor_ids = [r.content_id for r, _ in result.neighbors]
    assert "fss_q" not in neighbor_ids
    assert neighbor_ids[0] == "fss_dup"


@pytest.mark.asyncio
async def test_find_similar_raises_for_unknown_spot(db_session: AsyncSession) -> None:
    with pytest.raises(ResourceNotFound):
        await find_similar_spots(db_session, "ghost-not-real", limit=5)


@pytest.mark.asyncio
async def test_find_similar_empty_when_query_has_no_embedding(
    db_session: AsyncSession,
) -> None:
    await _seed_bare_spot(db_session, "fss_noemb")
    result = await find_similar_spots(db_session, "fss_noemb", limit=5)
    assert result.query.content_id == "fss_noemb"
    assert result.neighbors == []
