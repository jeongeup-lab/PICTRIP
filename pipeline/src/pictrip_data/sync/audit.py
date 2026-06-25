"""Owns the `sync_runs` audit table.

The backend admin console reads this table READ-ONLY. The pipeline is the sole
owner: it creates the table (CREATE TABLE IF NOT EXISTS) and is the only writer.
Do NOT add this table to backend Alembic. Column names are a shared contract with
the backend admin module — renaming breaks both sides.
"""

from __future__ import annotations

from contextlib import contextmanager
from collections.abc import Iterator

import psycopg

DDL = """
CREATE TABLE IF NOT EXISTS sync_runs (
    id            bigserial PRIMARY KEY,
    started_at    timestamptz NOT NULL DEFAULT now(),
    finished_at   timestamptz,
    status        text NOT NULL DEFAULT 'running',   -- running | success | error
    mode          text,
    watermark_from timestamptz,
    watermark_to  timestamptz,
    api_calls     int  NOT NULL DEFAULT 0,
    fetched       int  NOT NULL DEFAULT 0,
    inserted      int  NOT NULL DEFAULT 0,
    updated       int  NOT NULL DEFAULT 0,
    soft_deleted  int  NOT NULL DEFAULT 0,
    skipped       int  NOT NULL DEFAULT 0,
    duration_sec  double precision,
    error         text
);
CREATE INDEX IF NOT EXISTS idx_sync_runs_recent ON sync_runs (id DESC);
"""


def ensure_table(conn: psycopg.Connection) -> None:
    conn.execute(DDL)
    conn.commit()


@contextmanager
def record_run(conn: psycopg.Connection, mode: str) -> Iterator[dict[str, int]]:
    """Open a sync_runs row, yield a mutable counter dict, finalize on exit.

    TODO: insert a 'running' row, yield counters, then UPDATE with terminal
    status/finished_at/duration on success, or status='error' + message on raise.
    """
    ensure_table(conn)
    counters = {
        "api_calls": 0,
        "fetched": 0,
        "inserted": 0,
        "updated": 0,
        "soft_deleted": 0,
        "skipped": 0,
    }
    yield counters
