"""IMG ORM models. spot_embeddings = the 512-dim CLIP vector store (halfvec)."""

from __future__ import annotations

from datetime import datetime

from pgvector.sqlalchemy import HALFVEC
from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.embedding import EMBEDDING_DIM


class SpotEmbedding(Base):
    __tablename__ = "spot_embeddings"
    __table_args__ = (
        # HNSW serving index for halfvec cosine similarity (ADR-0006).
        # m / ef_construction match what migration 0005 created so autogenerate
        # treats the ORM declaration and the live DDL as equivalent — keeps
        # this PR's new index out of the existing autogenerate drift list.
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
