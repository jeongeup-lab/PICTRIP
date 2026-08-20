from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from time import monotonic
from typing import Any

from redis.asyncio import Redis, from_url

from app.config import settings
from app.core.db import async_session_factory
from app.modules.agent import toolloop
from app.modules.agent.services import ask as ask_service
from app.modules.agent.tools import ToolContext
from app.web.errors import AppError
from scripts.travel_golden_set import CASES, Case

TOP_N = 20


@dataclass(slots=True)
class Side:
    ids: list[str]
    tools: list[str]
    elapsed: float
    llm_calls: int
    error: str | None = None


@dataclass(slots=True)
class Comparison:
    cid: str
    group: str
    label: str
    question: str
    old: Side
    new: Side

    @property
    def overlap(self) -> float:
        if not self.old.ids and not self.new.ids:
            return 1.0
        if not self.old.ids or not self.new.ids:
            return 0.0
        shared = len(set(self.old.ids) & set(self.new.ids))
        return shared / len(set(self.old.ids) | set(self.new.ids))


def _question(case: Case) -> str | None:
    raw = case.payload.get("question")
    return raw if isinstance(raw, str) and raw else None


async def _old_side(session: Any, redis: Any, case: Case) -> Side:
    started = monotonic()
    try:
        response = await ask_service.ask(
            session,
            redis,
            None,
            question=_question(case),
            lat=case.payload.get("lat"),
            lng=case.payload.get("lng"),
            image_bytes=None,
            image_mime=None,
        )
    except AppError as exc:
        return Side(ids=[], tools=[], elapsed=monotonic() - started, llm_calls=1, error=exc.code)
    return Side(
        ids=[spot.contentId for spot in response.spots][:TOP_N],
        tools=[step.tool for step in response.steps],
        elapsed=monotonic() - started,
        llm_calls=sum(1 for step in response.steps if step.tool == "intent"),
    )


async def _new_side(session: Any, redis: Any, case: Case) -> Side:
    started = monotonic()
    ctx = ToolContext(
        session=session,
        redis=redis,
        kto=None,
        lat=case.payload.get("lat"),
        lng=case.payload.get("lng"),
    )
    try:
        trace = await toolloop.route(ctx, _question(case) or "")
    except AppError as exc:
        return Side(ids=[], tools=[], elapsed=monotonic() - started, llm_calls=1, error=exc.code)
    return Side(
        ids=[row.content_id for row in trace.rows][:TOP_N],
        tools=[step.tool for step in trace.steps],
        elapsed=trace.elapsed,
        llm_calls=trace.rounds + 1,
    )


async def compare(case: Case, redis: Redis) -> Comparison:
    async with async_session_factory() as session:
        old = await _old_side(session, redis, case)
    async with async_session_factory() as session:
        new = await _new_side(session, redis, case)
    return Comparison(
        cid=case.cid,
        group=case.group,
        label=case.label,
        question=_question(case) or "",
        old=old,
        new=new,
    )


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(len(ordered) * fraction))
    return ordered[index]


def summarise(rows: list[Comparison]) -> dict[str, Any]:
    strong = [row for row in rows if row.overlap >= 0.8]
    both_empty = [row for row in rows if not row.old.ids and not row.new.ids]
    lost = [row for row in rows if row.old.ids and not row.new.ids]
    gained = [row for row in rows if not row.old.ids and row.new.ids]
    return {
        "cases": len(rows),
        "overlap>=0.8": len(strong),
        "both_empty": len(both_empty),
        "old_only": len(lost),
        "new_only": len(gained),
        "old_p50_s": round(_percentile([row.old.elapsed for row in rows], 0.5), 2),
        "new_p50_s": round(_percentile([row.new.elapsed for row in rows], 0.5), 2),
        "old_p95_s": round(_percentile([row.old.elapsed for row in rows], 0.95), 2),
        "new_p95_s": round(_percentile([row.new.elapsed for row in rows], 0.95), 2),
        "old_llm_total": sum(row.old.llm_calls for row in rows),
        "new_llm_total": sum(row.new.llm_calls for row in rows),
    }


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare the deterministic router against the tool-calling loop."
    )
    parser.add_argument("--only", default=None, help="케이스 ID 접두사 또는 그룹명")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--json", default=None, help="비교 결과를 쓸 파일")
    args = parser.parse_args()

    picked = [case for case in CASES if _question(case)]
    if args.only:
        picked = [c for c in picked if c.cid.startswith(args.only) or args.only in c.group]
    if args.limit:
        picked = picked[: args.limit]

    redis: Redis = from_url(  # type: ignore[no-untyped-call]
        str(settings.REDIS_URL), encoding="utf-8", decode_responses=True
    )
    rows: list[Comparison] = []
    for case in picked:
        row = await compare(case, redis)
        rows.append(row)
        mark = "OK " if row.overlap >= 0.8 else "DIFF"
        print(
            f"{mark} {row.cid:<4} overlap={row.overlap:>4.0%} "
            f"old={len(row.old.ids):>3}/{row.old.elapsed:>4.1f}s "
            f"new={len(row.new.ids):>3}/{row.new.elapsed:>4.1f}s "
            f"| {row.label} | {' > '.join(row.new.tools) or '-'}"
        )

    await redis.aclose()
    report = summarise(rows)
    print("\n--- shadow summary ---")
    for key, value in report.items():
        print(f"  {key:>14}: {value}")

    if args.json:
        payload = {
            "summary": report,
            "cases": [
                {
                    "cid": row.cid,
                    "label": row.label,
                    "overlap": row.overlap,
                    "old": {"ids": row.old.ids, "tools": row.old.tools},
                    "new": {"ids": row.new.ids, "tools": row.new.tools},
                }
                for row in rows
            ],
        }
        await asyncio.to_thread(
            Path(args.json).write_text, json.dumps(payload, ensure_ascii=False, indent=1), "utf-8"
        )


if __name__ == "__main__":
    asyncio.run(main())
