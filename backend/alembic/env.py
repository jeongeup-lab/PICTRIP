"""Alembic environment for async SQLAlchemy 2.0.

All ORM models are imported here so `Base.metadata` is fully populated before
Alembic compares it to the live database.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.config import settings
from app.core.db import Base

# --- Import all models so Base.metadata is complete ---
# Side-effect imports: F401 is suppressed for the whole alembic/* tree via ruff
# per-file-ignores; no explicit noqa is needed (it would trigger RUF100).
from app.modules.images import models as _images_models
from app.modules.map import models as _map_models
from app.modules.spots import models as _spots_models
from app.modules.system import models as _system_models
from app.modules.taste import models as _taste_models
from app.modules.users import models as _users_models

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", settings.sqlalchemy_database_url)
target_metadata = Base.metadata


def include_object(object_, name, type_, reflected, compare_to):
    # `sync_runs` is owned by pipeline/ (CREATE TABLE IF NOT EXISTS in
    # pictrip_data/sync/audit.py). It is never a backend model; exclude it from
    # autogenerate so a drop is never emitted. (Monorepo invariant, CLAUDE.md.)
    return not (type_ == "table" and name == "sync_runs")


def run_migrations_offline() -> None:
    """Generate SQL without a live DB connection."""
    context.configure(
        url=settings.sqlalchemy_database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section) or {},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
