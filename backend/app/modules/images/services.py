"""IMG service layer. Owned by Dev A (CLIP) + Dev B (HNSW index DDL)."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def find_neighbor_content_ids(
    session: AsyncSession,
    content_id: str,
    *,
    limit: int = 10,
    region: str | None = None,
) -> list[tuple[str, float]]:
    """Top-N nearest neighbors of `content_id` by cosine distance over the
    pre-computed spot_embeddings.embedding (halfvec(512)).

    Returns (content_id, distance) tuples ordered by ascending distance.
    The query spot is excluded. If the query has no embedding row, returns
    an empty list (a signal, not an error — the caller decides UX).

    When `region` (a legal-dong sido code on spots.ldong_regn_cd) is given,
    neighbors are restricted to that sido (province). A plain HNSW scan only
    visits ~`hnsw.ef_search` candidates before the WHERE filter applies, so
    region spots beyond that
    horizon would be silently dropped — making a region with real matches look
    empty. For the filtered query we enable `hnsw.iterative_scan` so recall is
    bounded by the region, not the index horizon, and `strict_order` keeps the
    similarity ordering exact (pgvector ≥ 0.8, ADR-0014).
    """
    region_filter = "AND s.ldong_regn_cd = :region" if region else ""
    sql = text(
        f"""
        WITH q AS (
            SELECT embedding FROM spot_embeddings WHERE content_id = :cid
        )
        SELECT se.content_id,
               (se.embedding <=> (SELECT embedding FROM q))::float AS distance
        FROM spot_embeddings se
        JOIN spots s ON s.content_id = se.content_id
        WHERE se.content_id != :cid
          AND s.show_flag = 1
          {region_filter}
          AND EXISTS (SELECT 1 FROM q)
        ORDER BY se.embedding <=> (SELECT embedding FROM q)
        LIMIT :lim
        """
    )
    params: dict[str, object] = {"cid": content_id, "lim": limit}
    if region:
        # SET LOCAL is scoped to the current transaction, so the iterative scan
        # applies only to the ANN query below — concurrent requests on other
        # connections keep the global ef_search baseline (ADR-0006/0014).
        await session.execute(text("SET LOCAL hnsw.iterative_scan = strict_order"))
        params["region"] = region
    result = await session.execute(sql, params)
    return [(row.content_id, float(row.distance)) for row in result]


async def find_neighbors_by_vector(
    session: AsyncSession,
    embedding: list[float],
    *,
    limit: int = 10,
) -> list[tuple[str, float]]:
    """Top-N nearest active spots for an arbitrary query vector (e.g. a freshly
    CLIP-embedded user photo) by cosine distance over spot_embeddings.embedding
    (halfvec(512)).

    Mirrors `find_neighbor_content_ids` but binds the query vector directly
    instead of looking it up from an existing row — so no row is excluded.
    Returns (content_id, distance) tuples ordered by ascending distance. An
    empty `embedding` yields an empty list (a signal, not an error).
    """
    if not embedding:
        return []

    literal = "[" + ",".join(repr(float(v)) for v in embedding) + "]"
    sql = text(
        """
        SELECT se.content_id,
               (se.embedding <=> (:emb)::halfvec(512))::float AS distance
        FROM spot_embeddings se
        JOIN spots s ON s.content_id = se.content_id
        WHERE s.show_flag = 1
        ORDER BY se.embedding <=> (:emb)::halfvec(512)
        LIMIT :lim
        """
    )
    result = await session.execute(sql, {"emb": literal, "lim": limit})
    return [(row.content_id, float(row.distance)) for row in result]


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
