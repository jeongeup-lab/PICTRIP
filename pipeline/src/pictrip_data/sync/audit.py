"""Owns the `sync_runs` audit table.

The backend admin console reads this table READ-ONLY. The pipeline is the sole
owner: it creates the table (CREATE TABLE IF NOT EXISTS) and is the only writer.
Do NOT add this table to backend Alembic. Column names are a shared contract with
the backend admin module — renaming breaks both sides.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime

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
def record_run(conn: psycopg.Connection, mode: str) -> Iterator[dict]:
    """Open a sync_runs row, yield a mutable counter dict, finalize on exit.

    INSERTs a 'running' row and commits it immediately so the audit row exists
    independently of the run's data work. On clean exit UPDATEs the same row to
    status='success' with finished_at/duration/watermark/counters; on exception
    rolls back the data work, UPDATEs to status='error' with the message, and
    re-raises.
    """
    ensure_table(conn)
    counters: dict = {
        "api_calls": 0,
        "fetched": 0,
        "inserted": 0,
        "updated": 0,
        "soft_deleted": 0,
        "skipped": 0,
        "watermark_from": None,
        "watermark_to": None,
    }
    cur = conn.cursor()
    cur.execute("INSERT INTO sync_runs (status, mode) VALUES ('running', %s) RETURNING id", (mode,))
    run_id = cur.fetchone()[0]
    conn.commit()
    start = time.monotonic()
    try:
        yield counters
    except Exception as exc:
        conn.rollback()
        cur.execute(
            "UPDATE sync_runs SET status='error', finished_at=now(), "
            "duration_sec=%s, error=%s WHERE id=%s",
            (time.monotonic() - start, str(exc)[:2000], run_id),
        )
        conn.commit()
        raise
    else:
        cur.execute(
            "UPDATE sync_runs SET status='success', finished_at=now(), duration_sec=%s, "
            "watermark_from=%s, watermark_to=%s, api_calls=%s, fetched=%s, inserted=%s, "
            "updated=%s, soft_deleted=%s, skipped=%s WHERE id=%s",
            (
                time.monotonic() - start,
                counters["watermark_from"],
                counters["watermark_to"],
                counters["api_calls"],
                counters["fetched"],
                counters["inserted"],
                counters["updated"],
                counters["soft_deleted"],
                counters["skipped"],
                run_id,
            ),
        )
        conn.commit()


def last_success_watermark(conn: psycopg.Connection) -> datetime | None:
    """Return the newest watermark_to among status='success' runs, else None."""
    cur = conn.cursor()
    cur.execute(
        "SELECT watermark_to FROM sync_runs WHERE status='success' AND watermark_to IS NOT NULL "
        "ORDER BY watermark_to DESC LIMIT 1"
    )
    row = cur.fetchone()
    return row[0] if row else None
