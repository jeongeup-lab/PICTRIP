from __future__ import annotations

from datetime import datetime

from pgvector.sqlalchemy import HALFVEC
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Identity,
    Index,
    Integer,
    SmallInteger,
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


class OverseasSpotMatch(Base):
    """해외 게시물 → 국내 매칭 3곳의 사전계산 결과.

    content_id 만 담고 제목·이미지는 읽을 때 spots 에 조인한다 — 이미지가 바뀌어도
    깨진 URL 이 나갈 수 없고, 스팟이 숨겨지면 조인에서 그냥 빠진다.
    """

    __tablename__ = "overseas_spot_matches"

    overseas_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("overseas_spots.id", ondelete="CASCADE"), primary_key=True
    )
    rank: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    content_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("spots.content_id", ondelete="CASCADE"), nullable=False
    )
    distance: Mapped[float] = mapped_column(Float, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("rank BETWEEN 1 AND 3", name="ck_overseas_spot_matches_rank_range"),
        Index("idx_overseas_spot_matches_content", "content_id"),
    )
