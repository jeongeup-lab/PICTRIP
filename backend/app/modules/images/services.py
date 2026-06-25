"""IMG service layer. Owned by Dev A (CLIP) + Dev B (HNSW index DDL)."""

from __future__ import annotations

# Thin seam: queries live in repositories; services re-exports so existing
# callers (taste/services, curations) keep their import path unchanged.
from app.modules.images.repositories import (
    find_neighbor_ids_by_vector_direct,
    spot_has_embedding_clause,
)

__all__ = ["find_neighbor_ids_by_vector_direct", "spot_has_embedding_clause"]
