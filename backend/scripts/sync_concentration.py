from __future__ import annotations

import argparse
import asyncio
import os
from datetime import datetime

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.db import async_session_factory
from app.core.logging import get_logger
from app.modules.spots.models import (
    Sigungu,
    Spot,
    SpotConcentration,
    SpotConcentrationDaily,
)

logger = get_logger(__name__)

_OPERATION = "tatsCnctrRatedList"
_NUM_OF_ROWS = 20000


def _normalize(name: str) -> str:
    return "".join(name.split()).lower()


def _ssl_verify() -> bool:
    return os.environ.get("KTO_SSL_VERIFY", "true").strip().lower() not in {"false", "0", "no"}


async def _fetch_sigungu(
    client: httpx.AsyncClient, area_cd: str, signgu_cd: str
) -> list[dict[str, str]]:
    params = {
        "serviceKey": settings.KTO_SERVICE_KEY,
        "MobileOS": "ETC",
        "MobileApp": settings.KTO_MOBILE_APP,
        "_type": "json",
        "numOfRows": str(_NUM_OF_ROWS),
        "pageNo": "1",
        "areaCd": area_cd,
        "signguCd": signgu_cd,
    }
    url = f"{settings.KTO_BASE_URL_CNCTR}/{_OPERATION}"
    resp = await client.get(url, params=params)
    resp.raise_for_status()
    payload = resp.json()
    response = payload.get("response", {})
    header = response.get("header", {})
    if header.get("resultCode") not in {"0000", "00", None}:
        logger.warning(
            "cnctr.fetch.nonzero",
            signgu=signgu_cd,
            msg=header.get("resultMsg"),
            raw=str(payload)[:200],
        )
        return []
    items = response.get("body", {}).get("items")
    if not items or items == "":
        return []
    item = items.get("item", [])
    return item if isinstance(item, list) else [item]


def _collection_day_rate(rows: list[dict[str, str]]) -> dict[str, tuple[float, str]]:
    best: dict[str, tuple[str, float]] = {}
    for r in rows:
        name = (r.get("tAtsNm") or "").strip()
        ymd = r.get("baseYmd") or ""
        rate_raw = r.get("cnctrRate")
        if not name or not ymd or rate_raw in (None, ""):
            continue
        try:
            rate = float(rate_raw)
        except (TypeError, ValueError):
            continue
        prev = best.get(name)
        if prev is None or ymd < prev[0]:
            best[name] = (ymd, rate)
    return {name: (rate, ymd) for name, (ymd, rate) in best.items()}


async def persist_rows(session: AsyncSession, rows: list[dict[str, object]]) -> None:
    """스냅샷과 원장에 함께 쓴다 — 스냅샷은 덮어써야 하고 원장은 쌓여야 한다."""
    snapshot = pg_insert(SpotConcentration).values(rows)
    await session.execute(
        snapshot.on_conflict_do_update(
            index_elements=[SpotConcentration.content_id],
            set_={
                "concentration_rate": snapshot.excluded.concentration_rate,
                "base_ymd": snapshot.excluded.base_ymd,
                "raw_name": snapshot.excluded.raw_name,
                "signgu_cd": snapshot.excluded.signgu_cd,
                "collected_at": datetime.now().astimezone(),
            },
        )
    )

    history = pg_insert(SpotConcentrationDaily).values(
        [
            {
                "content_id": row["content_id"],
                "base_ymd": row["base_ymd"],
                "concentration_rate": row["concentration_rate"],
            }
            for row in rows
        ]
    )
    await session.execute(
        history.on_conflict_do_update(
            index_elements=[SpotConcentrationDaily.content_id, SpotConcentrationDaily.base_ymd],
            set_={"concentration_rate": history.excluded.concentration_rate},
        )
    )


async def main() -> None:
    parser = argparse.ArgumentParser(description="Load KTO 집중률 into spot_concentration.")
    parser.add_argument("--limit", type=int, default=None, help="only the first N sigungu")
    parser.add_argument("--dry-run", action="store_true", help="fetch + match, no DB writes")
    args = parser.parse_args()

    async with async_session_factory() as session:
        sigungus = list(
            (await session.execute(select(Sigungu).order_by(Sigungu.ldong_signgu_cd)))
            .scalars()
            .all()
        )
    if args.limit:
        sigungus = sigungus[: args.limit]

    totals = {"sigungu": 0, "empty": 0, "fetched": 0, "matched": 0, "upserted": 0, "errors": 0}
    upsert_rows: list[dict[str, object]] = []

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(30.0, connect=10.0),
        verify=_ssl_verify(),
        headers={"User-Agent": f"{settings.KTO_MOBILE_APP}/1.0"},
    ) as client:
        for sg in sigungus:
            totals["sigungu"] += 1
            try:
                rows = await _fetch_sigungu(client, sg.ldong_regn_cd, sg.ldong_signgu_cd)
            except Exception as exc:
                totals["errors"] += 1
                logger.warning("cnctr.fetch.failed", signgu=sg.ldong_signgu_cd, error=str(exc))
                continue
            if not rows:
                totals["empty"] += 1
                continue

            day_rates = _collection_day_rate(rows)
            totals["fetched"] += len(day_rates)

            async with async_session_factory() as session:
                spot_rows = (
                    await session.execute(
                        select(Spot.content_id, Spot.title).where(
                            Spot.ldong_signgu_cd == sg.ldong_signgu_cd,
                            Spot.show_flag == 1,
                            Spot.first_image_url.is_not(None),
                        )
                    )
                ).all()
            by_norm: dict[str, str] = {}
            for content_id, title in spot_rows:
                by_norm.setdefault(_normalize(title), content_id)

            for name, (rate, ymd) in day_rates.items():
                content_id = by_norm.get(_normalize(name))
                if content_id is None:
                    continue
                totals["matched"] += 1
                upsert_rows.append(
                    {
                        "content_id": content_id,
                        "concentration_rate": round(rate, 2),
                        "base_ymd": datetime.strptime(ymd, "%Y%m%d").date(),
                        "raw_name": name[:255],
                        "signgu_cd": sg.ldong_signgu_cd,
                    }
                )

    deduped: dict[str, dict[str, object]] = {}
    for row in upsert_rows:
        cid = row["content_id"]
        cur = deduped.get(cid)
        if cur is None or row["concentration_rate"] > cur["concentration_rate"]:
            deduped[cid] = row
    final_rows = list(deduped.values())

    if args.dry_run:
        print(f"[dry-run] would upsert {len(final_rows)} rows")
        _print_summary(totals, final_rows)
        return

    if final_rows:
        async with async_session_factory() as session:
            await persist_rows(session, final_rows)
            await session.commit()
        totals["upserted"] = len(final_rows)

    _print_summary(totals, final_rows)


def _print_summary(totals: dict[str, int], final_rows: list[dict[str, object]]) -> None:
    top = sorted(final_rows, key=lambda r: r["concentration_rate"], reverse=True)[:10]
    print("--- 집중률 sync summary ---")
    for k, v in totals.items():
        print(f"  {k:>9}: {v}")
    print(f"  {'unique':>9}: {len(final_rows)}")
    if top:
        print("  top 10:")
        for r in top:
            print(f"    {r['concentration_rate']:>6}  {r['raw_name']}  ({r['content_id']})")


if __name__ == "__main__":
    asyncio.run(main())
