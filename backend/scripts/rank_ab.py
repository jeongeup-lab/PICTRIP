from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import text

from app.core.db import AsyncSession, async_session_factory
from app.modules.agent import repositories
from app.modules.agent.repositories import CandidateRow

TOP_N = 5
CANDIDATE_LIMIT = 400

THEMES: dict[str, repositories.BuzzTheme] = {
    "attraction": "spot",
    "cafe": "cafe",
    "food": "food",
}

_REGION_SQL = """
SELECT r.ldong_regn_nm || ' ' || g.ldong_signgu_nm AS prefix, count(*) AS n
FROM spots s
JOIN regions r ON r.ldong_regn_cd = s.ldong_regn_cd
JOIN sigungus g ON g.ldong_signgu_cd = s.ldong_signgu_cd
WHERE s.show_flag = 1
  AND s.first_image_url IS NOT NULL AND s.first_image_url <> ''
GROUP BY 1 HAVING count(*) >= :floor
ORDER BY n DESC
LIMIT :lim
"""

_METRIC_SQL = """
SELECT
  count(*) FILTER (WHERE b.blog_total > 0)              AS famed,
  count(*) FILTER (WHERE v.aesthetic_score IS NOT NULL) AS visual,
  count(*) FILTER (WHERE sc.content_id IS NOT NULL)     AS crowded,
  count(*) FILTER (WHERE sd.overview IS NOT NULL)       AS detailed,
  COALESCE(avg(b.blog_total), 0)::float8                AS avg_fame,
  count(DISTINCT g.ldong_signgu_cd)                     AS sigungus
FROM spots s
LEFT JOIN sigungus g ON g.ldong_signgu_cd = s.ldong_signgu_cd
LEFT JOIN spot_buzz b ON b.content_id = s.content_id AND b.scope = 'base'
LEFT JOIN spot_visual v ON v.content_id = s.content_id
LEFT JOIN spot_concentration sc ON sc.content_id = s.content_id
LEFT JOIN spot_details sd ON sd.content_id = s.content_id
WHERE s.content_id = ANY(CAST(:ids AS text[]))
"""


@dataclass
class Shape:
    prefix: str
    pool: str


@dataclass
class Metrics:
    famed: int = 0
    visual: int = 0
    crowded: int = 0
    detailed: int = 0
    avg_fame: float = 0.0
    sigungus: int = 0
    seen: int = 0

    def add(self, row: Any) -> None:
        self.famed += int(row.famed)
        self.visual += int(row.visual)
        self.crowded += int(row.crowded)
        self.detailed += int(row.detailed)
        self.avg_fame += float(row.avg_fame)
        self.sigungus += int(row.sigungus)
        self.seen += 1

    def as_dict(self) -> dict[str, float]:
        n = max(self.seen, 1)
        return {
            "유명세 보유": round(self.famed / n, 2),
            "사진 감도": round(self.visual / n, 2),
            "혼잡도 보유": round(self.crowded / n, 2),
            "상세 캐시": round(self.detailed / n, 2),
            "평균 blog_total": round(self.avg_fame / n, 1),
            "시군구 다양성": round(self.sigungus / n, 2),
        }


@dataclass
class Report:
    shapes: int = 0
    changed: int = 0
    overlap: list[int] = field(default_factory=list)
    legacy: Metrics = field(default_factory=Metrics)
    scored: Metrics = field(default_factory=Metrics)


async def _shapes(session: AsyncSession, *, regions: int, floor: int) -> list[Shape]:
    rows = (await session.execute(text(_REGION_SQL), {"floor": floor, "lim": regions})).all()
    return [Shape(prefix=row.prefix, pool=pool) for row in rows for pool in THEMES]


async def _top(session: AsyncSession, shape: Shape, *, scored: bool) -> list[str]:
    from app.modules.spots.services import NearbyCategory, category_sql

    pool_sql = category_sql(NearbyCategory(shape.pool))
    rows: list[CandidateRow] = await repositories.find_candidates(
        session,
        codes=None,
        region_prefixes=[shape.prefix],
        limit=CANDIDATE_LIMIT,
        order="id",
        pool_sql=pool_sql,
        theme=THEMES[shape.pool],
        scored=scored,
    )
    return [row.content_id for row in rows[:TOP_N]]


async def _metrics(session: AsyncSession, ids: list[str], into: Metrics) -> None:
    if not ids:
        return
    row = (await session.execute(text(_METRIC_SQL), {"ids": ids})).one()
    into.add(row)


async def run(*, regions: int, floor: int) -> Report:
    report = Report()
    async with async_session_factory() as session:
        shapes = await _shapes(session, regions=regions, floor=floor)
        for shape in shapes:
            legacy = await _top(session, shape, scored=False)
            scored = await _top(session, shape, scored=True)
            if not legacy and not scored:
                continue
            report.shapes += 1
            hit = len(set(legacy) & set(scored))
            report.overlap.append(hit)
            if legacy[:TOP_N] != scored[:TOP_N]:
                report.changed += 1
            await _metrics(session, legacy, report.legacy)
            await _metrics(session, scored, report.scored)
    return report


def render(report: Report) -> str:
    n = max(report.shapes, 1)
    avg_overlap = sum(report.overlap) / n
    lines = [
        f"질의 형태          {report.shapes}개",
        f"top-{TOP_N} 변동     {report.changed}개 ({report.changed / n * 100:.0f}%)",
        f"평균 유지 개수      {avg_overlap:.2f} / {TOP_N}",
        "",
        f"{'지표':<16}{'구(md5)':>12}{'신(점수)':>12}   변화",
    ]
    before, after = report.legacy.as_dict(), report.scored.as_dict()
    for key in before:
        delta = after[key] - before[key]
        arrow = "↑" if delta > 0 else ("↓" if delta < 0 else "=")
        lines.append(f"{key:<16}{before[key]:>12}{after[key]:>12}   {arrow} {delta:+.2f}")
    return "\n".join(lines)


async def main() -> None:
    parser = argparse.ArgumentParser(description="랭킹 A/B — 구 md5 셔플 대비 신 점수 정렬")
    parser.add_argument("--regions", type=int, default=30)
    parser.add_argument("--floor", type=int, default=40)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = await run(regions=args.regions, floor=args.floor)
    if args.json:
        print(
            json.dumps(
                {
                    "shapes": report.shapes,
                    "changed": report.changed,
                    "legacy": report.legacy.as_dict(),
                    "scored": report.scored.as_dict(),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return
    print(render(report))


if __name__ == "__main__":
    asyncio.run(main())
