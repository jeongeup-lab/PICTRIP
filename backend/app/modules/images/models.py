from __future__ import annotations

from datetime import datetime

from pgvector.sqlalchemy import HALFVEC
from sqlalchemy import DateTime, ForeignKey, Index, Integer, SmallInteger, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.ml.embedding import EMBEDDING_DIM


class SpotEmbedding(Base):
    __tablename__ = "spot_embeddings"
    __table_args__ = (
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


class SpotEmbeddingGallery(Base):
    __tablename__ = "spot_embeddings_gallery"
    __table_args__ = (
        Index(
            "idx_spot_embeddings_gallery_hnsw",
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
    image_url: Mapped[str] = mapped_column(String(500), nullable=False)
    image_count: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class EmbeddingFailure(Base):
    __tablename__ = "embedding_failures"
    __table_args__ = (Index("idx_embedding_failures_reason", "reason"),)

    content_id: Mapped[str] = mapped_column(
        ForeignKey("spots.content_id", ondelete="CASCADE"), primary_key=True
    )
    reason: Mapped[str] = mapped_column(String(32), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, server_default="1", nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    first_failed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
