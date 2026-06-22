"""Idempotent seeder for the home-feed curations — 6 region heroes + 3 mood rails.

Inserts the first-class ``curations`` rows that back ``GET /home/feed`` (S07
§3.1/§3.2). Hero copy (title/subtitle) is taken **verbatim** from the design SSOT
``docs/mockups/05-home.html`` — the ``\n`` line break in each hero title is
preserved exactly (the client renders it with ``white-space: pre-line``).

Handpicks (``curation_spots``) are intentionally left empty: the quality-gate
random pool in ``app.modules.spots.services.curations`` fills each rail/hero until
hand-curated spots are loaded later. ``cover_spot_id`` is left null too — the feed
falls back to the resolved pool's first spot, and the client shows inset-gray when
nothing resolves.

    uv run python -m scripts.seed_curations             # seed (idempotent)
    uv run python -m scripts.seed_curations --dry-run   # print plan, no writes

Idempotency: ``INSERT ... ON CONFLICT (slug) DO NOTHING`` against the unique
``uq_curations_slug`` constraint, so a second run inserts nothing.
"""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import async_session_factory
from app.modules.spots.models import Curation

# ---- 6 region heroes -------------------------------------------------------
# region_cd = regions.ldong_regn_cd (sido, 2-digit): 제주=50 부산=26 강원=51
# 전북=52 경북=47 전남=46. title/subtitle verbatim from docs/mockups/05-home.html.
_REGION_CURATIONS: list[dict[str, object]] = [
    {
        "slug": "region-jeju",
        "title": "제주, 매일 가도\n새로운 섬",
        "subtitle": "제주에서 가장 사진 잘 받는 곳 →",
        "region_cd": "50",
    },
    {
        "slug": "region-busan",
        "title": "바다 끝에서\n부산",
        "subtitle": "해안선부터 야경까지, 부산 한 바퀴 →",
        "region_cd": "26",
    },
    {
        "slug": "region-gangneung",
        "title": "동해 보러\n강릉",
        "subtitle": "파도 소리 들리는 동해 스폿 →",
        "region_cd": "51",
    },
    {
        "slug": "region-jeonju",
        "title": "느리게 걷는\n전주",
        "subtitle": "한옥 골목을 천천히 걷기 →",
        "region_cd": "52",
    },
    {
        "slug": "region-gyeongju",
        "title": "천년을 걷는\n경주",
        "subtitle": "시간이 멈춘 듯한 신라의 도시 →",
        "region_cd": "47",
    },
    {
        "slug": "region-yeosu",
        "title": "밤바다의\n여수",
        "subtitle": "불빛 가득한 남해 항구 →",
        "region_cd": "46",
    },
]

# ---- 3 mood rails ----------------------------------------------------------
# mood_id = moods.id: sea=1 hanok=5 mountain=2. title/subtitle = the three rail
# section headers verbatim from docs/mockups/05-home.html.
_MOOD_CURATIONS: list[dict[str, object]] = [
    {
        "slug": "mood-sea",
        "title": "바다 보러 갈까요",
        "subtitle": "파도 소리가 좋은 해변과 카페",
        "mood_id": 1,
    },
    {
        "slug": "mood-hanok",
        "title": "골목을 천천히",
        "subtitle": "한옥과 오래된 거리",
        "mood_id": 5,
    },
    {
        "slug": "mood-mountain",
        "title": "산 위의 풍경",
        "subtitle": "조금 올라가면 보이는 것들",
        "mood_id": 2,
    },
]


def _rows() -> list[dict[str, object]]:
    """Build the full INSERT payload with type/position/is_published set."""
    rows: list[dict[str, object]] = []
    for pos, c in enumerate(_REGION_CURATIONS):
        rows.append(
            {
                "type": "region",
                "slug": c["slug"],
                "title": c["title"],
                "subtitle": c["subtitle"],
                "region_cd": c["region_cd"],
                "mood_id": None,
                "is_published": True,
                "position": pos,
            }
        )
    for pos, c in enumerate(_MOOD_CURATIONS):
        rows.append(
            {
                "type": "mood",
                "slug": c["slug"],
                "title": c["title"],
                "subtitle": c["subtitle"],
                "region_cd": None,
                "mood_id": c["mood_id"],
                "is_published": True,
                "position": pos,
            }
        )
    return rows


async def seed(session: AsyncSession) -> int:
    """Insert the 9 curations idempotently; return the number of rows inserted.

    ``ON CONFLICT (slug) DO NOTHING`` makes a second run a no-op. The session is
    injected (not committed here) so tests can pass a rolled-back fixture; the
    ``main()`` wrapper owns the commit.
    """
    stmt = (
        pg_insert(Curation)
        .values(_rows())
        .on_conflict_do_nothing(index_elements=[Curation.slug])
        .returning(Curation.id)
    )
    result = await session.execute(stmt)
    return len(result.scalars().all())


async def main() -> None:
    parser = argparse.ArgumentParser(description="Seed 6 region + 3 mood curations (idempotent).")
    parser.add_argument("--dry-run", action="store_true", help="print the plan, no DB writes")
    args = parser.parse_args()

    rows = _rows()
    if args.dry_run:
        print(f"[dry-run] would seed {len(rows)} curations (ON CONFLICT slug DO NOTHING):")
        for r in rows:
            scope = (
                f"region_cd={r['region_cd']}"
                if r["type"] == "region"
                else f"mood_id={r['mood_id']}"
            )
            print(f"  [{r['type']:>6}] {r['slug']:<16} pos={r['position']} {scope}")
        return

    async with async_session_factory() as session:
        inserted = await seed(session)
        await session.commit()
    print(f"inserted {inserted} curations ({len(rows) - inserted} already present)")


if __name__ == "__main__":
    asyncio.run(main())
