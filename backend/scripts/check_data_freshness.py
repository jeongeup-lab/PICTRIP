from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass

from sqlalchemy import text

from app.core.db import async_session_factory


@dataclass(frozen=True)
class Check:
    name: str
    sql: str
    max_age_hours: float
    why: str


CHECKS: tuple[Check, ...] = (
    Check(
        "spots.modified_time",
        "SELECT max(modified_time) FROM spots",
        24 * 14,
        "KTO 증분이 워터마크에 갇히면 잡은 계속 success 를 찍는다",
    ),
    Check(
        "sync_runs.incremental",
        "SELECT max(finished_at) FROM sync_runs WHERE status = 'success' AND mode = 'incremental'",
        26,
        "일일 DAG 가 아예 안 돌았는지",
    ),
    Check(
        "spot_concentration.collected_at",
        "SELECT max(collected_at) FROM spot_concentration",
        24 * 3,
        "Hot/Hidden 채널 신선도",
    ),
    Check(
        "overseas_spots.updated_at",
        "SELECT min(updated_at) FROM overseas_spots",
        24 * 70,
        "월간 DAG 는 Kuma 하트비트 상한(24일)을 넘어 push 모니터를 못 붙인다",
    ),
)


async def _age_hours(session, sql: str) -> float | None:
    row = (
        await session.execute(text(f"SELECT EXTRACT(EPOCH FROM (now() - ({sql})))/3600"))
    ).scalar()
    return float(row) if row is not None else None


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="적재가 멈췄는데 잡은 success 를 찍는 상태를 잡는다."
    )
    parser.add_argument("--warn-only", action="store_true", help="stale 이어도 0 으로 끝낸다")
    args = parser.parse_args()

    stale: list[str] = []
    async with async_session_factory() as session:
        for check in CHECKS:
            age = await _age_hours(session, check.sql)
            if age is None:
                stale.append(f"{check.name}: 값 없음 — {check.why}")
                print(f"  FAIL {check.name:32s} (empty)")
                continue
            ok = age <= check.max_age_hours
            print(
                f"  {'ok  ' if ok else 'FAIL'} {check.name:32s} "
                f"{age:8.1f}h / {check.max_age_hours:.0f}h"
            )
            if not ok:
                stale.append(f"{check.name}: {age:.1f}h 경과 — {check.why}")

    if not stale:
        print("data freshness: ok")
        return
    print("--- stale ---")
    for line in stale:
        print(f"  {line}")
    if not args.warn_only:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
