from __future__ import annotations

import argparse
import asyncio

from app.modules.spots.visual_job import run_visual_job


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="spot_embeddings에 CLIP 텍스트 앵커를 대조해 spot_visual(사진유형·미학점수)을 채운다. API 콜 0."
    )
    parser.add_argument(
        "--limit", type=int, default=None, help="이번 실행에서 점수 낼 최대 스팟 수"
    )
    args = parser.parse_args()

    result = await run_visual_job(limit=args.limit)

    print("--- visual score summary ---")
    print(f"  {'scored':>10}: {result.scored}")
    for key, val in sorted(result.by_type.items()):
        print(f"  {key:>10}: {val}")


if __name__ == "__main__":
    asyncio.run(main())
