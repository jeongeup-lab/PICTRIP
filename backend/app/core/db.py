"""Async SQLAlchemy 2.0 setup with asyncpg.

`Base` is the declarative base imported by all module models.
`async_session` is the request-scoped session factory exposed via `get_db`.
`DbSession` is the FastAPI dependency-typed alias used by route signatures,
so routes can stay free of sqlalchemy imports (see ADR-0002 / ADR-0004 +
backend/pyproject.toml `[tool.importlinter]`).
"""

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
        # ADR-0006: HNSW serving uses ef_search=80 as the recall/latency baseline.
        # Pushed in via asyncpg server_settings so it's set once per physical
        # connection — no per-session SET, no race with pooled reuse.
        connect_args={"server_settings": {"hnsw.ef_search": "80"}},
    )


engine: AsyncEngine = _build_engine()

async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an async session.

    Rolls back on uncaught exceptions; commit must be explicit at the service layer.
    """
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


# Routes import this alias instead of sqlalchemy.ext.asyncio.AsyncSession
# directly — keeps routes free of ORM imports per ADR-0002.
DbSession = Annotated[AsyncSession, Depends(get_db)]
