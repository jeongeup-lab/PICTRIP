from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from sqlalchemy import text

from app.core.db import async_session_factory

_UPSERT_SQL = """
INSERT INTO spot_buzz
    (content_id, scope, mentions, distinct_blogs, recent_ratio, blog_total, fetched_at)
VALUES (:content_id, 'base', 0, 0, :recent_ratio, :blog_total, now())
ON CONFLICT (content_id, scope) DO UPDATE SET
    recent_ratio = EXCLUDED.recent_ratio,
    blog_total = EXCLUDED.blog_total,
    fetched_at = now()
"""


async def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "스팟 전수 스캔 JSONL(content_id·blog_total·recent_90d)을 "
            "spot_buzz scope='base' 베이스라인으로 적재한다."
        )
    )
    parser.add_argument("jsonl", type=Path, nargs="+")
    args = parser.parse_args()

    written = 0
    async with async_session_factory() as session:
        for path in args.jsonl:
            for line in path.read_text().splitlines():
                row = json.loads(line)
                total = row.get("blog_total")
                if not row.get("content_id") or total is None:
                    continue
                bare = row.get("bare_total") or 0
                study = row.get("study") or 0
                plug = row.get("plug") or 0
                if total > 700_000:
                    continue
                if bare > 200_000 and total > 300_000:
                    continue
                if study > total or plug > total:
                    continue
                recent = row.get("recent_90d") or 0
                await session.execute(
                    text(_UPSERT_SQL),
                    {
                        "content_id": row["content_id"],
                        "recent_ratio": min(recent, 100) / 100,
                        "blog_total": total,
                    },
                )
                written += 1
        await session.commit()
    print(f"baseline rows upserted: {written}")


if __name__ == "__main__":
    asyncio.run(main())
