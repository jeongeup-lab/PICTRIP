"""IMG service layer. Owned by Dev A (CLIP) + Dev B (HNSW index DDL)."""

from __future__ import annotations

# Thin seam: queries live in repositories; services re-exports so existing
# callers (taste/services, curations) keep their import path unchanged.
from app.modules.images.embedding_job import (
    EmbedResult,
    collect_targets,
    count_missing,
    embed_spots,
    run_embedding_job,
)
from app.modules.images.embedding_lock import (
    EMBEDDING_JOB_LOCK_NAME,
    EmbeddingJobLock,
    acquire_embedding_job_lock,
    release_embedding_job_lock,
)
from app.modules.images.repositories import (
    find_neighbor_ids_by_vector_direct,
    spot_has_embedding_clause,
)

__all__ = [
    "EMBEDDING_JOB_LOCK_NAME",
    "EmbedResult",
    "EmbeddingJobLock",
    "acquire_embedding_job_lock",
    "collect_targets",
    "count_missing",
    "embed_spots",
    "find_neighbor_ids_by_vector_direct",
    "release_embedding_job_lock",
    "run_embedding_job",
    "spot_has_embedding_clause",
]
