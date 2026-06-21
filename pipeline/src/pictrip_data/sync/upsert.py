"""Spots upsert / soft-delete logic."""

from __future__ import annotations

from typing import Any

import psycopg


def upsert_spots(
    conn: psycopg.Connection,
    rows: list[dict[str, Any]],
    counters: dict[str, int],
) -> None:
    """Upsert a batch of KTO spot records into `spots`.

    TODO: INSERT ... ON CONFLICT (content_id) DO UPDATE; track inserted/updated
    in counters. Image URLs are stored as-is (never downloaded). overview is
    NOT touched here (backend caches detailCommon2 verbatim).
    """
    _ = (conn, rows, counters)
