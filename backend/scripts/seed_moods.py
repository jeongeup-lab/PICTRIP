"""Standalone moods seeder — kept as a fallback to the Alembic data migration.

Normally `alembic upgrade head` already inserts the 8 moods. Use this only
if Alembic seed was rolled back or for one-off local resets.

    uv run python -m scripts.seed_moods
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.core.db import async_session_factory
from app.modules.spots.models import Mood

_SEED = [
    (1, "sea", "바다", "🌊", 1),
    (2, "mountain", "산·숲", "⛰️", 2),
    (3, "lake", "호수", "🏞️", 3),
    (4, "island", "섬", "🏝️", 4),
    (5, "hanok", "한옥·고궁", "🏛️", 5),
    (6, "night", "야경", "🌃", 6),
    (7, "market", "시장", "🛍️", 7),
    (8, "street", "도시 골목", "🏙️", 8),
]


async def main() -> None:
    async with async_session_factory() as s:
        existing = {m.code for m in (await s.execute(select(Mood))).scalars().all()}
        rows = [
            Mood(id=i, code=c, name=n, emoji=e, sort_order=o)
            for i, c, n, e, o in _SEED
            if c not in existing
        ]
        if not rows:
            print("moods already seeded")
            return
        s.add_all(rows)
        await s.commit()
        print(f"inserted {len(rows)} moods")


if __name__ == "__main__":
    asyncio.run(main())
