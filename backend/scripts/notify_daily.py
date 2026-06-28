"""Post the daily pipeline report card to Discord.

    uv run python -m scripts.notify_daily

Runs after the daily spots sync (CT111) and embedding backfill (CT112). Reads
the DB and posts an ANSI report card to ``DISCORD_WEBHOOK_URL`` summarising
TODAY's aggregated sync_runs (a day may have several runs) plus current
embedding coverage. No-op when the webhook is unset. Green on a clean day;
red + ``@here`` if any of today's runs failed or none ran at all.
"""

from __future__ import annotations

import asyncio
import datetime
from typing import Any

import httpx
from sqlalchemy import text

from app.config import settings
from app.core.db import async_session_factory
from app.core.logging import get_logger

logger = get_logger(__name__)

_ESC = chr(27)
_R = _ESC + "[0m"
_B = _ESC + "[1;37m"
_GREEN = _ESC + "[1;32m"
_RED = _ESC + "[1;31m"
_GN = _ESC + "[32m"
_ADMIN = "https://api.pictrip.org/admin"


def _bar(pct: float, n: int = 9) -> str:
    k = round(pct / 100 * n)
    return "█" * k + "░" * (n - k)


def _fw(w: str | None) -> str:
    """KTO watermark text 'YYYYMMDDHHMMSS' -> 'MM·DD HH:MM'."""
    return f"{w[4:6]}·{w[6:8]} {w[8:10]}:{w[10:12]}" if w and len(w) == 14 else (w or "-")


def build_payload(
    agg: dict[str, Any],
    wm: tuple[str | None, str | None],
    cov: float,
    spots: int,
    miss: int,
    today_emb: int,
    now_kst: str,
) -> dict[str, Any]:
    """Pure: assemble the Discord webhook payload from metrics."""
    ok = agg["ok"] and agg["runs"] > 0
    head = _GREEN if ok else _RED
    bar_color = _GN if ok else _RED
    label = "성공" if ok else "점검 필요"
    mark = "🟢" if ok else "🔴"
    rows = [
        _B
        + "수집"
        + _R
        + f"     신규 {agg['ins']}   수정 {agg['upd']}   삭제 {agg['soft']}   ({agg['runs']}회)",
        _B + "호출" + _R + f"     {agg['api']} API",
        _B
        + "임베딩"
        + _R
        + "   "
        + bar_color
        + _bar(cov)
        + _R
        + f" {cov:.1f}%   +{today_emb:,} 오늘 · 잔여 {miss:,}",
        _B + "현황" + _R + f"     활성 {spots:,} · 커버리지 {cov:.1f}%",
        _B + "워터마크" + _R + f" {_fw(wm[0])} -> {_fw(wm[1])}",
    ]
    body = (
        "```ansi\n"
        + head
        + f"{mark} PicTrip 일일 파이프라인 — {label}"
        + _R
        + "\n\n"
        + "\n".join(rows)
        + "\n```"
    )
    payload: dict[str, Any] = {
        "username": "PicTrip 파이프라인",
        "embeds": [
            {
                "color": 5763719 if ok else 15548997,
                "description": body + f"\n🔗 [어드민 콘솔 열기]({_ADMIN})",
                "footer": {"text": f"PicTrip · {now_kst} KST"},
                "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
            }
        ],
    }
    if not ok:
        payload["content"] = "@here ⚠️ 파이프라인 점검 필요"
    return payload


async def _collect() -> dict[str, Any]:
    async with async_session_factory() as s:
        a = (
            await s.execute(
                text(
                    "SELECT count(*), coalesce(sum(inserted),0), coalesce(sum(updated),0), "
                    "coalesce(sum(soft_deleted),0), coalesce(sum(api_calls),0), "
                    "coalesce(bool_and(status='success'), false) FROM sync_runs "
                    "WHERE (started_at AT TIME ZONE 'Asia/Seoul')::date "
                    "= (now() AT TIME ZONE 'Asia/Seoul')::date"
                )
            )
        ).first()
        agg = {"runs": a[0], "ins": a[1], "upd": a[2], "soft": a[3], "api": a[4], "ok": a[5]}
        wm_row = (
            await s.execute(
                text("SELECT watermark_from, watermark_to FROM sync_runs ORDER BY id DESC LIMIT 1")
            )
        ).first()
        wm = (wm_row[0], wm_row[1]) if wm_row else (None, None)
        spots = (await s.execute(text("SELECT count(*) FROM spots WHERE show_flag=1"))).scalar_one()
        img = (
            await s.execute(
                text(
                    "SELECT count(*) FROM spots WHERE first_image_url IS NOT NULL AND first_image_url<>''"
                )
            )
        ).scalar_one()
        miss = (
            await s.execute(
                text(
                    "SELECT count(*) FROM spots s WHERE s.first_image_url IS NOT NULL "
                    "AND s.first_image_url<>'' AND NOT EXISTS "
                    "(SELECT 1 FROM spot_embeddings e WHERE e.content_id=s.content_id)"
                )
            )
        ).scalar_one()
        today_emb = (
            await s.execute(
                text(
                    "SELECT count(*) FROM spot_embeddings WHERE computed_at > now() - interval '18 hours'"
                )
            )
        ).scalar_one()
        now_kst = (
            await s.execute(text("SELECT to_char(now() AT TIME ZONE 'Asia/Seoul','MM-DD HH24:MI')"))
        ).scalar_one()
    cov = (img - miss) / img * 100 if img else 0.0
    return {
        "agg": agg,
        "wm": wm,
        "cov": cov,
        "spots": spots,
        "miss": miss,
        "today_emb": today_emb,
        "now_kst": now_kst,
    }


async def main() -> None:
    if not settings.DISCORD_WEBHOOK_URL:
        logger.info("notify.skip", reason="no webhook configured")
        return
    m = await _collect()
    payload = build_payload(
        m["agg"], m["wm"], m["cov"], m["spots"], m["miss"], m["today_emb"], m["now_kst"]
    )
    async with httpx.AsyncClient() as client:
        resp = await client.post(settings.DISCORD_WEBHOOK_URL, json=payload, timeout=15.0)
        resp.raise_for_status()
    logger.info("notify.sent", status=resp.status_code, coverage=round(m["cov"], 1))


if __name__ == "__main__":
    asyncio.run(main())
