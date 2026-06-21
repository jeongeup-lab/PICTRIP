"""IMG service layer. Owned by Dev A (CLIP) + Dev B (HNSW index DDL)."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def find_neighbor_ids_by_vector_direct(
    session: AsyncSession,
    embedding: list[float],
    *,
    limit: int = 30,
) -> list[tuple[str, float]]:
    """HNSW-direct top-N for an arbitrary query vector over the BASE
    spot_embeddings table (no JOIN/CTE in the ranked query).

    S07 §10: ``SELECT content_id FROM spot_embeddings ORDER BY embedding <=> $1
    LIMIT n`` against the bare base table so the planner is free to use the HNSW
    index scan; ``show_flag`` filtering + metadata join happen *afterward* by the
    returned content_ids (the caller hydrates cards via SPT). Binding the vector
    with ``CAST(:emb AS halfvec(512))`` avoids the asyncpg ``::``/bind-param
    colon clash. Returns ``(content_id, distance)`` ordered by ascending cosine
    distance; an empty ``embedding`` yields an empty list.
    """
    if not embedding:
        return []

    literal = "[" + ",".join(repr(float(v)) for v in embedding) + "]"
    sql = text(
        """
        SELECT content_id,
               (embedding <=> CAST(:emb AS halfvec(512)))::float AS distance
        FROM spot_embeddings
        ORDER BY embedding <=> CAST(:emb AS halfvec(512))
        LIMIT :lim
        """
    )
    result = await session.execute(sql, {"emb": literal, "lim": limit})
    return [(row.content_id, float(row.distance)) for row in result]
