"""Async SQLAlchemy 2.0 setup with asyncpg."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

# AsyncSession re-exported so services type their session param without importing sqlalchemy (ADR-0002).
__all__ = ["AsyncSession", "Base", "DbSession", "engine", "get_db"]


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def _build_engine() -> AsyncEngine:
    return create_async_engine(
        settings.sqlalchemy_database_url,
        echo=settings.DEBUG,
        pool_size=20,
        max_overflow=30,
        pool_timeout=30,
        pool_recycle=1800,
        pool_pre_ping=True,
        # hnsw.ef_search=80 set as asyncpg server_setting (once per connection, no per-session SET race). ADR-0006.
        connect_args={"server_settings": {"hnsw.ef_search": "80"}},
    )


engine: AsyncEngine = _build_engine()

async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async session; rolls back on error, commit is explicit in services."""
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


# Route-facing alias so routes stay free of sqlalchemy imports (ADR-0002).
DbSession = Annotated[AsyncSession, Depends(get_db)]
