"""Process version + uptime, captured once at import.

`API_VERSION` is the single source the FastAPI app title, ``/meta/version`` and
the admin health endpoint all read, so the version string isn't hardcoded in
three places. ``uptime_seconds()`` measures wall-clock seconds since the module
was first imported (≈ process start), used by ``/admin/api/health``.
"""

from __future__ import annotations

import time

API_VERSION = "1.0.0-dev"

# Captured at import (≈ app boot). monotonic() is immune to wall-clock jumps.
_STARTED_MONOTONIC = time.monotonic()


def uptime_seconds() -> int:
    return int(time.monotonic() - _STARTED_MONOTONIC)
