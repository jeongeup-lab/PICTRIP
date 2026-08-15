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
