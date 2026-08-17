from __future__ import annotations

import argparse
import asyncio

from app.modules.spots.buzz_job import run_buzz_job


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="지역x테마 블로그 그리드로 spot_buzz를 갱신한다 (시도 17 x 테마 3 x 정렬 2 ≈ 102콜)."
    )
    parser.add_argument("--regions", nargs="*", default=None, help="시도 단축명 (예: 제주 부산)")
    parser.add_argument("--themes", nargs="*", default=None, help="spot cafe food 중 일부")
    parser.add_argument("--pause", type=float, default=0.15)
    args = parser.parse_args()

    result = await run_buzz_job(regions=args.regions, themes=args.themes, pause=args.pause)

    print("--- buzz sync summary ---")
    print(f"  {'queries':>14}: {result.queries}")
    print(f"  {'posts':>14}: {result.posts}")
    print(f"  {'rows_upserted':>14}: {result.rows}")
    print(f"  {'scopes':>14}: {len(result.scopes)}")


if __name__ == "__main__":
    asyncio.run(main())
