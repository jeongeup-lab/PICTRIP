from __future__ import annotations

import argparse
import asyncio

from app.core.db import async_session_factory
from app.modules.feed.services import precompute_matches


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Precompute domestic matches for every embedded overseas spot."
    )
    parser.add_argument("--limit", type=int, default=None, help="only the first N overseas rows")
    parser.add_argument(
        "--only-missing", action="store_true", help="skip rows that already have matches"
    )
    args = parser.parse_args()

    async with async_session_factory() as session:
        counters = await precompute_matches(
            session, limit=args.limit, only_missing=args.only_missing
        )

    print("--- overseas match precompute summary ---")
    for key in ("targets", "matched", "empty"):
        print(f"  {key:>8}: {counters[key]}")


if __name__ == "__main__":
    asyncio.run(main())
