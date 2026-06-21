"""One-shot loader for region / classification master codes."""

from __future__ import annotations

from pictrip_data.db import connect


def load_codes() -> None:
    """Load lcls_systm / region master codes into their tables.

    TODO: idempotent upsert from KTO code endpoints. Run manually, not on cron.
    """
    with connect() as conn:
        _ = conn
