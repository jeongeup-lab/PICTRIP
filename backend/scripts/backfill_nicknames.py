"""Backfill random nicknames for accounts created before the generator shipped.

Accounts created before 2026-07-01 stored the provider name claim, which is
often absent — those rows kept ``users.name = NULL`` and the app falls back to
the generic '여행자' label. New signups already get a random nickname at
creation (``app.modules.users.nickname``); this fills the remaining NULLs the
same way. Soft-deleted accounts are skipped: deletion scrubs ``name`` on
purpose. Connects with the same ``DATABASE_URL`` / ``POSTGRES_*`` settings as
the app (``app.config``).

Usage (from ``backend/``):

    uv run python -m scripts.backfill_nicknames             # write
    uv run python -m scripts.backfill_nicknames --dry-run   # count only

Idempotent: only touches ``name IS NULL`` rows, and each UPDATE re-checks both
``name IS NULL`` and ``deleted_at IS NULL`` so neither a signup nor an account
deletion racing the script is ever overwritten.
"""

from __future__ import annotations

import argparse
import asyncio
import random

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import async_session_factory, engine
from app.modules.users.nickname import generate_nickname

_SELECT_NAMELESS = "SELECT id FROM users WHERE name IS NULL AND deleted_at IS NULL ORDER BY id"


async def backfill(session: AsyncSession, rng: random.Random | None = None) -> int:
    """Assign a random nickname to every active user without one; return the count."""
    ids = (await session.execute(text(_SELECT_NAMELESS))).scalars().all()
    for user_id in ids:
        await session.execute(
            text(
                "UPDATE users SET name = :n WHERE id = :i AND name IS NULL AND deleted_at IS NULL"
            ),
            {"n": generate_nickname(rng), "i": user_id},
        )
    return len(ids)


async def _run(dry_run: bool) -> None:
    async with async_session_factory() as session:
        if dry_run:
            count = (
                await session.execute(text(f"SELECT count(*) FROM ({_SELECT_NAMELESS}) q"))
            ).scalar_one()
            print(f"would backfill {count} user(s) (dry run, no writes).")
        else:
            count = await backfill(session)
            await session.commit()
            print(f"backfilled {count} user(s).")
    await engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill random nicknames for name-less users.")
    parser.add_argument("--dry-run", action="store_true", help="count affected rows, write nothing")
    args = parser.parse_args()
    asyncio.run(_run(args.dry_run))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
