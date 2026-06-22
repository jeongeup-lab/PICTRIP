"""IMG DTOs."""

from __future__ import annotations

from pydantic import BaseModel


class EmbeddingStatus(BaseModel):
    totalSpots: int
    embedded: int
    pending: int
