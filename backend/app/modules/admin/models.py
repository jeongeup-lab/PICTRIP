"""admin ORM models — ``admin_users`` (console credentials).

The admin console authenticates against a DB-stored credential instead of an env
var (decision 2026-06-27: drop ``ADMIN_PASSWORD`` so the credential lives in the
shared CT110 DB — provisioning/rotation needs only DB write, no CT112 .env/shell).
Scoped to the admin module; the password is a bcrypt hash (``app.core.passwords``).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class AdminUser(Base):
    """A single admin-console login (username + bcrypt password hash)."""

    __tablename__ = "admin_users"

    username: Mapped[str] = mapped_column(String(64), primary_key=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
