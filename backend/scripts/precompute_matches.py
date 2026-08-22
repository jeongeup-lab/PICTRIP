from __future__ import annotations

import asyncio

from app.core.db import async_session_factory
from app.modules.feed.services import precompute_matches


async def main() -> None:
    async with async_session_factory() as session:
        counters = await precompute_matches(session)

    print("--- overseas match precompute summary ---")
    for key in ("targets", "matched", "empty"):
        print(f"  {key:>8}: {counters[key]}")


if __name__ == "__main__":
    asyncio.run(main())
