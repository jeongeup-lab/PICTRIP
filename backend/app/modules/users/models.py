"""USR ORM models. See DB schema §Section 1."""

from __future__ import annotations

from datetime import datetime

from pgvector.sqlalchemy import HALFVEC
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    false,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.core.embedding import EMBEDDING_DIM


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        Index(
            "idx_users_email_active",
            "email",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "idx_users_taste_vector",
            "taste_vector",
            postgresql_using="ivfflat",
            postgresql_ops={"taste_vector": "halfvec_cosine_ops"},
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    bio: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location_label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    profile_image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    taste_vector: Mapped[list[float] | None] = mapped_column(HALFVEC(EMBEDDING_DIM), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    auth_providers: Mapped[list[UserAuthProvider]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    consent: Mapped[UserConsent | None] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )


class UserAuthProvider(Base):
    __tablename__ = "user_auth_providers"
    __table_args__ = (
        CheckConstraint(
            "provider IN ('kakao','google','apple','email')",
            name="ck_auth_provider_value",
        ),
        UniqueConstraint(
            "provider",
            "provider_user_id",
            name="uq_auth_provider_account",
        ),
        Index("idx_auth_providers_user", "user_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(16), nullable=False)
    provider_user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    refresh_token_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    linked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="auth_providers")


class UserConsent(Base):
    __tablename__ = "user_consents"

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    location_consent: Mapped[bool] = mapped_column(Boolean, server_default=false(), nullable=False)
    photo_consent: Mapped[bool] = mapped_column(Boolean, server_default=false(), nullable=False)
    # NOTE: the `notification_consent` DB column still exists (dropped in M3 /
    # Task 20). Its ORM mapping was removed here (expand/contract) so this image
    # stops referencing it; it has a DB default (false) so INSERTs that omit it
    # still succeed.
    terms_version: Mapped[str] = mapped_column(String(16), nullable=False)
    consented_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="consent")
