"""IMG ORM models. spot_embeddings = the 512-dim CLIP vector store (halfvec)."""

from __future__ import annotations

from datetime import datetime

from pgvector.sqlalchemy import HALFVEC
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.embedding import EMBEDDING_DIM


class SpotEmbedding(Base):
    __tablename__ = "spot_embeddings"
    __table_args__ = (
        # HNSW cosine index (ADR-0006); m/ef_construction must match migration 0005 to avoid autogenerate drift.
        Index(
            "idx_spot_embeddings_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "halfvec_cosine_ops"},
            postgresql_with={"m": 16, "ef_construction": 128},
        ),
    )

    content_id: Mapped[str] = mapped_column(
        ForeignKey("spots.content_id", ondelete="CASCADE"), primary_key=True
    )
    embedding: Mapped[list[float]] = mapped_column(HALFVEC(EMBEDDING_DIM), nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class EmbeddingFailure(Base):
    """A spot whose embedding attempt failed — the persistent record that lets the
    admin console distinguish a *failed* embedding from a *not-yet-attempted* one.

    Collection (pipeline → spots) and embedding (CLIP → spot_embeddings) are
    separate steps; a spot with ``first_image_url`` but no ``spot_embeddings`` row
    is otherwise indistinguishable between "pending" and "broken image". The embed
    job upserts a row here on failure (incrementing ``attempts``) and DELETEs it on
    a later success, so ``count(*)`` here = the live failure backlog.
    """

    __tablename__ = "embedding_failures"
    __table_args__ = (Index("idx_embedding_failures_reason", "reason"),)

    content_id: Mapped[str] = mapped_column(
        ForeignKey("spots.content_id", ondelete="CASCADE"), primary_key=True
    )
    # download_failed (non-200/empty body) | clip_error (decode/inference raised)
    reason: Mapped[str] = mapped_column(String(32), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, server_default="1", nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    first_failed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
