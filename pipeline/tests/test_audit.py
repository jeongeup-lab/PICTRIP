"""Tests for the sync_runs audit table (DDL + run lifecycle)."""

import pytest

from pictrip_data.sync.audit import ensure_table, last_success_watermark, record_run


def _latest(conn):
    cur = conn.cursor()
    cur.execute(
        "SELECT status, fetched, inserted, duration_sec FROM sync_runs ORDER BY id DESC LIMIT 1"
    )
    return cur.fetchone()


def test_record_run_success(db_conn):
    ensure_table(db_conn)
    with record_run(db_conn, "daily") as c:
        c["fetched"] = 5
        c["inserted"] = 5
    status, fetched, inserted, duration = _latest(db_conn)
    assert status == "success"
    assert (fetched, inserted) == (5, 5)
    assert duration is not None and duration >= 0


def test_record_run_error_reraises(db_conn):
    ensure_table(db_conn)
    with pytest.raises(ValueError):
        with record_run(db_conn, "daily"):
            raise ValueError("boom")
    assert _latest(db_conn)[0] == "error"


def test_last_success_watermark_none_when_empty(db_conn):
    ensure_table(db_conn)
    assert last_success_watermark(db_conn) is None


def test_last_success_watermark_round_trip(db_conn):
    ensure_table(db_conn)
    # Watermark is the raw KTO modifiedtime text 'YYYYMMDDHHMMSS'.
    wm = "20260627043000"
    with record_run(db_conn, "daily") as c:
        c["watermark_to"] = wm
    assert last_success_watermark(db_conn) == wm
