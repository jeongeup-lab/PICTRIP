from __future__ import annotations

import time

API_VERSION = "1.0.0-dev"

_STARTED_MONOTONIC = time.monotonic()


def uptime_seconds() -> int:
    return int(time.monotonic() - _STARTED_MONOTONIC)
