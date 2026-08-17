from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Mood(Base):
    __tablename__ = "moods"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(32), nullable=False)
    emoji: Mapped[str] = mapped_column(String(8), nullable=False)
    sort_order: Mapped[int] = mapped_column(SmallInteger, nullable=False)


class Region(Base):
    __tablename__ = "regions"

    ldong_regn_cd: Mapped[str] = mapped_column(String(8), primary_key=True)
    ldong_regn_nm: Mapped[str] = mapped_column(String(50), nullable=False)


class Sigungu(Base):
    __tablename__ = "sigungus"

    ldong_signgu_cd: Mapped[str] = mapped_column(String(8), primary_key=True)
    ldong_regn_cd: Mapped[str] = mapped_column(
        String(8), ForeignKey("regions.ldong_regn_cd"), nullable=False, index=True
    )
    ldong_signgu_nm: Mapped[str] = mapped_column(String(50), nullable=False)


class LclsSystmCode(Base):
    __tablename__ = "lcls_systm_codes"

    lcls_systm3_cd: Mapped[str] = mapped_column(String(16), primary_key=True)
    lcls_systm2_cd: Mapped[str | None] = mapped_column(String(16), nullable=True)
    lcls_systm1_cd: Mapped[str | None] = mapped_column(String(16), nullable=True)
    lcls_systm3_nm: Mapped[str] = mapped_column(String(100), nullable=False)
    lcls_systm2_nm: Mapped[str | None] = mapped_column(String(100), nullable=True)
    lcls_systm1_nm: Mapped[str | None] = mapped_column(String(100), nullable=True)


class Spot(Base):
    __tablename__ = "spots"
    __table_args__ = (
        CheckConstraint(
            "cpyrht_div_cd IS NULL OR cpyrht_div_cd IN ('Type1','Type3')",
            name="ck_spot_cpyrht_div_cd",
        ),
        CheckConstraint("show_flag IN (0, 1)", name="ck_spot_show_flag"),
        Index(
            "idx_spots_active_location",
            "mapx",
            "mapy",
            postgresql_where=text("show_flag = 1"),
        ),
        Index(
            "idx_spots_active_region",
            "ldong_regn_cd",
            "ldong_signgu_cd",
            postgresql_where=text("show_flag = 1"),
        ),
        Index(
            "idx_spots_active_lcls",
            "lcls_systm3",
            postgresql_where=text("show_flag = 1"),
        ),
        Index(
            "idx_spots_active_type",
            "content_type_id",
            postgresql_where=text("show_flag = 1"),
        ),
        Index("idx_spots_modified", text("modified_time DESC")),
        Index(
            "idx_spots_visible",
            "show_flag",
            postgresql_where=text("show_flag = 1"),
        ),
        Index(
            "idx_spots_image_pool",
            "ldong_regn_cd",
            postgresql_where=text("show_flag = 1 AND first_image_url IS NOT NULL"),
        ),
    )

    content_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    content_type_id: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    addr1: Mapped[str | None] = mapped_column(String(255), nullable=True)
    addr2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    zipcode: Mapped[str | None] = mapped_column(String(16), nullable=True)
    mapx: Mapped[Decimal | None] = mapped_column(Numeric(11, 8), nullable=True)
    mapy: Mapped[Decimal | None] = mapped_column(Numeric(10, 8), nullable=True)
    ldong_regn_cd: Mapped[str | None] = mapped_column(
        String(8), ForeignKey("regions.ldong_regn_cd"), nullable=True
    )
    ldong_signgu_cd: Mapped[str | None] = mapped_column(
        String(8), ForeignKey("sigungus.ldong_signgu_cd"), nullable=True
    )
    lcls_systm1: Mapped[str | None] = mapped_column(String(16), nullable=True)
    lcls_systm2: Mapped[str | None] = mapped_column(String(16), nullable=True)
    lcls_systm3: Mapped[str | None] = mapped_column(
        String(16), ForeignKey("lcls_systm_codes.lcls_systm3_cd"), nullable=True
    )
    cpyrht_div_cd: Mapped[str | None] = mapped_column(String(8), nullable=True)
    first_image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    first_image2_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    show_flag: Mapped[int] = mapped_column(SmallInteger, server_default=text("1"), nullable=False)
    modified_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SpotDetail(Base):
    __tablename__ = "spot_details"
    __table_args__ = (Index("idx_spot_details_cached", "cached_at"),)

    content_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("spots.content_id", ondelete="CASCADE"),
        primary_key=True,
    )
    content_type_id: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    intro_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    info_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    overview: Mapped[str | None] = mapped_column(Text, nullable=True)
    homepage: Mapped[str | None] = mapped_column(String(500), nullable=True)
    tel: Mapped[str | None] = mapped_column(String(50), nullable=True)
    cached_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SpotImage(Base):
    __tablename__ = "spot_images"
    __table_args__ = (
        UniqueConstraint("content_id", "sort_order", name="uq_spot_images_content_sort"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    content_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("spots.content_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    origin_image_url: Mapped[str] = mapped_column(String(500), nullable=False)
    small_image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cpyrht_div_cd: Mapped[str | None] = mapped_column(String(8), nullable=True)
    serial_num: Mapped[str | None] = mapped_column(String(32), nullable=True)
    sort_order: Mapped[int] = mapped_column(SmallInteger, server_default=text("0"), nullable=False)


class SpotMood(Base):
    __tablename__ = "spot_moods"
    __table_args__ = (
        CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0",
            name="ck_spot_mood_confidence",
        ),
        CheckConstraint(
            "source IN ('code','image','manual')",
            name="ck_spot_mood_source",
        ),
        Index("idx_spot_moods_mood", "mood_id", text("confidence DESC")),
    )

    content_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("spots.content_id", ondelete="CASCADE"),
        primary_key=True,
    )
    mood_id: Mapped[int] = mapped_column(SmallInteger, ForeignKey("moods.id"), primary_key=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)


class SpotConcentration(Base):
    __tablename__ = "spot_concentration"
    __table_args__ = (
        CheckConstraint(
            "concentration_rate >= 0 AND concentration_rate <= 100",
            name="ck_spot_concentration_rate_range",
        ),
        Index("idx_spot_concentration_rate", text("concentration_rate DESC")),
    )

    content_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("spots.content_id", ondelete="CASCADE"),
        primary_key=True,
    )
    concentration_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    base_ymd: Mapped[date] = mapped_column(Date, nullable=False)
    raw_name: Mapped[str] = mapped_column(String(255), nullable=False)
    signgu_cd: Mapped[str | None] = mapped_column(String(8), nullable=True)
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SpotBuzz(Base):
    __tablename__ = "spot_buzz"
    __table_args__ = (Index("idx_spot_buzz_scope", "scope", "mentions"),)

    content_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    scope: Mapped[str] = mapped_column(String(48), primary_key=True)
    mentions: Mapped[int] = mapped_column(nullable=False, server_default="0")
    distinct_blogs: Mapped[int] = mapped_column(nullable=False, server_default="0")
    recent_ratio: Mapped[float] = mapped_column(Float, nullable=False, server_default="0")
    blog_total: Mapped[int | None] = mapped_column(nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SpotVisual(Base):
    __tablename__ = "spot_visual"
    __table_args__ = (Index("idx_spot_visual_score", "photo_type", "aesthetic_score"),)

    content_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    photo_type: Mapped[str] = mapped_column(String(16), nullable=False)
    aesthetic_score: Mapped[float] = mapped_column(Float, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class UserSavedSpot(Base):
    __tablename__ = "user_saved_spots"
    __table_args__ = (Index("idx_user_saved_spots_user", "user_id", text("saved_at DESC")),)

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    content_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("spots.content_id", ondelete="CASCADE"),
        primary_key=True,
    )
    saved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
