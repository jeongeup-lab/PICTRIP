"""KST time helpers (curation daily cache reuses the next-midnight TTL)."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")


def kst_now() -> datetime:
    return datetime.now(tz=KST)


def seconds_until_kst_midnight(now: datetime) -> int:
    """TTL so a cached value expires exactly at the next KST midnight."""
    tomorrow = (now + timedelta(days=1)).date()
    midnight = datetime.combine(tomorrow, datetime.min.time(), tzinfo=KST)
    return max(1, int((midnight - now).total_seconds()))
