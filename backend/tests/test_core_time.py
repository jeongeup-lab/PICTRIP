from datetime import datetime
from zoneinfo import ZoneInfo

from app.core.time import KST, seconds_until_kst_midnight


def test_ttl_is_seconds_until_next_kst_midnight():
    now = datetime(2026, 6, 21, 23, 0, 0, tzinfo=KST)  # 23:00 KST → 1h to midnight
    assert seconds_until_kst_midnight(now) == 3600


def test_ttl_never_zero_at_midnight_boundary():
    now = datetime(2026, 6, 21, 0, 0, 0, tzinfo=KST)
    assert seconds_until_kst_midnight(now) == 86400


def test_kst_is_seoul():
    assert ZoneInfo("Asia/Seoul") == KST
