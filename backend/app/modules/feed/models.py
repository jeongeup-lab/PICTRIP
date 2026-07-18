from __future__ import annotations

from datetime import datetime

from pgvector.sqlalchemy import HALFVEC
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    Identity,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.ml.embedding import EMBEDDING_DIM


class OverseasSpot(Base):
    __tablename__ = "overseas_spots"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    wikidata_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name_ko: Mapped[str] = mapped_column(String(255), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(255))
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    country_name_ko: Mapped[str] = mapped_column(String(80), nullable=False)
    description_ko: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str] = mapped_column(Text, nullable=False)
    image_author: Mapped[str | None] = mapped_column(Text)
    image_license: Mapped[str | None] = mapped_column(String(80))
    image_license_url: Mapped[str | None] = mapped_column(Text)
    image_source_url: Mapped[str] = mapped_column(Text, nullable=False)
    fame_score: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    category: Mapped[str | None] = mapped_column(String(40))
    lat: Mapped[float | None] = mapped_column(Float)
    lng: Mapped[float | None] = mapped_column(Float)
    embedding: Mapped[list[float] | None] = mapped_column(HALFVEC(EMBEDDING_DIM))
    is_hidden: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index(
            "idx_overseas_spots_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "halfvec_cosine_ops"},
            postgresql_with={"m": 16, "ef_construction": 128},
        ),
        Index("idx_overseas_spots_visible", "is_hidden", text("fame_score DESC")),
    )
