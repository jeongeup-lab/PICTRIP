from __future__ import annotations

import argparse
import asyncio

from app.core.db import async_session_factory
from app.modules.spots.prewarm_job import collect_prewarm_targets, run_prewarm_job


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prewarm spot_details.overview via KTO detailCommon2 (1 call per spot)."
    )
    parser.add_argument("--limit", type=int, default=800, help="spots per run (KTO quota budget)")
    parser.add_argument("--pause", type=float, default=0.0, help="seconds between KTO calls")
    parser.add_argument("--dry-run", action="store_true", help="count targets, no KTO/write")
    args = parser.parse_args()

    if args.dry_run:
        async with async_session_factory() as session:
            targets = await collect_prewarm_targets(session, limit=args.limit)
            remaining = len(await collect_prewarm_targets(session))
        print(f"targets this run: {len(targets)}")
        print(f"still missing overview: {remaining}")
        return

    result = await run_prewarm_job(limit=args.limit, pause_seconds=args.pause)

    async with async_session_factory() as session:
        remaining = len(await collect_prewarm_targets(session))

    print("--- detail prewarm summary ---")
    print(f"  {'written':>16}: {result.written}")
    for key, val in sorted(result.by_status.items()):
        print(f"  {key:>16}: {val}")
    print(f"  {'still_missing':>16}: {remaining}")


if __name__ == "__main__":
    asyncio.run(main())
