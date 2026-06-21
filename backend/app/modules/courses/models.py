"""CRS ORM models. See DB schema §Section 6."""

from __future__ import annotations

from datetime import date, datetime, time

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    Time,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Course(Base):
    __tablename__ = "courses"
    __table_args__ = (Index("idx_courses_user", "user_id", text("updated_at DESC")),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    base_content_id: Mapped[str | None] = mapped_column(
        String(32),
        ForeignKey("spots.content_id", ondelete="SET NULL"),
        nullable=True,
    )
    duration_type: Mapped[str] = mapped_column(String(16), nullable=False)
    pace_type: Mapped[str] = mapped_column(String(16), nullable=False)
    companion_type: Mapped[str] = mapped_column(String(16), nullable=False)
    course_type: Mapped[str] = mapped_column(String(16), nullable=False)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class CourseDay(Base):
    __tablename__ = "course_days"
    __table_args__ = (UniqueConstraint("course_id", "day_number", name="uq_course_day_number"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    day_number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    total_km: Mapped[float | None] = mapped_column(Numeric(7, 2), nullable=True)
    estimated_hours: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)


class CourseItem(Base):
    __tablename__ = "course_items"
    __table_args__ = (Index("idx_course_items_day", "course_day_id", "position"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    course_day_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("course_days.id", ondelete="CASCADE"),
        nullable=False,
    )
    content_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("spots.content_id", ondelete="RESTRICT"),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    scheduled_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    stay_minutes: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
