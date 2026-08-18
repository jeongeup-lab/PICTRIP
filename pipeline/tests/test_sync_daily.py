import json
from datetime import date
from pathlib import Path

import pytest

from pictrip_data.sync.audit import ensure_table
from pictrip_data.sync.daily import (
    PartialFullSync,
    WatermarkTooOld,
    _run,
    sync_daily,
    sync_dates,
    sync_full,
    watermark_param,
)

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "sync_list_response.json").read_text())
ITEMS = FIXTURE["response"]["body"]["items"]["item"]


class FakeClient:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def area_based_sync_list(self, *, page, rows=100, modifiedtime=None):
        self.calls.append((page, modifiedtime))
        return self.pages.get(page, ([], 2))


def test_watermark_param_slices_date():
    assert watermark_param("20260627043000") == "20260627"
    assert watermark_param(None) is None
    assert watermark_param("") is None


def test_sync_daily_pages_until_empty_and_records(seed_refs):
    conn = seed_refs
    ensure_table(conn)
    client = FakeClient({1: (ITEMS, 2)})
    sync_daily(mode="daily", client=client, conn=conn)

    cur = conn.cursor()
    cur.execute("SELECT status, fetched FROM sync_runs ORDER BY id DESC LIMIT 1")
    status, fetched = cur.fetchone()
    assert status == "success"
    assert fetched == 2
    cur.execute("SELECT show_flag FROM spots WHERE content_id='3509884'")
    assert cur.fetchone()[0] == 1
    cur.execute("SELECT show_flag FROM spots WHERE content_id='2865520'")
    assert cur.fetchone()[0] == 0


def _seed_active_spot(conn, content_id):
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO spots (content_id, content_type_id, title, ldong_regn_cd, "
        "ldong_signgu_cd, lcls_systm3, show_flag) "
        "VALUES (%s, 15, 'gone', '11', '11110', 'EV010600', 1) "
        "ON CONFLICT (content_id) DO UPDATE SET show_flag = 1",
        (content_id,),
    )
    conn.commit()


def test_sync_full_reconcile_hides_vanished(seed_refs):
    conn = seed_refs
    ensure_table(conn)
    _seed_active_spot(conn, "T_GONE")
    client = FakeClient({1: (ITEMS, 2)})
    sync_full(client=client, conn=conn)

    cur = conn.cursor()
    cur.execute("SELECT show_flag FROM spots WHERE content_id='T_GONE'")
    assert cur.fetchone()[0] == 0
    cur.execute("SELECT content_id FROM spots WHERE content_id IN ('2865520','3509884')")
    assert {r[0] for r in cur.fetchall()} == {"2865520", "3509884"}


def test_sync_full_empty_seen_skips_reconcile(seed_refs):
    conn = seed_refs
    ensure_table(conn)
    _seed_active_spot(conn, "T_KEEP")
    client = FakeClient({})
    sync_full(client=client, conn=conn)

    cur = conn.cursor()
    cur.execute("SELECT show_flag FROM spots WHERE content_id='T_KEEP'")
    assert cur.fetchone()[0] == 1
    cur.execute("SELECT soft_deleted FROM sync_runs ORDER BY id DESC LIMIT 1")
    assert cur.fetchone()[0] == 0


def test_sync_full_refuses_soft_delete_on_partial_fetch(seed_refs):
    conn = seed_refs
    ensure_table(conn)
    for n in range(10):
        _seed_active_spot(conn, f"T_KEEP{n}")
    client = FakeClient({1: (ITEMS, 2)})

    with pytest.raises(PartialFullSync):
        sync_full(client=client, conn=conn)

    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM spots WHERE content_id LIKE 'T_KEEP%' AND show_flag = 1")
    assert cur.fetchone()[0] == 10
    cur.execute("SELECT status, soft_deleted FROM sync_runs ORDER BY id DESC LIMIT 1")
    assert cur.fetchone() == ("error", 0)


def test_sync_dates_walks_each_day_to_today():
    assert sync_dates("20260626183808", date(2026, 6, 29)) == [
        "20260626",
        "20260627",
        "20260628",
        "20260629",
    ]


def test_sync_dates_full_when_no_watermark():
    assert sync_dates(None, date(2026, 6, 29)) == [None]


def test_sync_dates_refuses_stale_watermark():
    with pytest.raises(WatermarkTooOld):
        sync_dates("20260101000000", date(2026, 6, 29))


def test_watermark_advances_when_the_day_had_no_changes(seed_refs):
    conn = seed_refs
    ensure_table(conn)
    client = FakeClient({})
    _run("incremental", ["20260701", "20260702"], client, conn, watermark_from="20260701120000")

    cur = conn.cursor()
    cur.execute("SELECT watermark_to FROM sync_runs ORDER BY id DESC LIMIT 1")
    assert cur.fetchone()[0] == "20260702000000"


def test_watermark_never_regresses_below_watermark_from(seed_refs):
    conn = seed_refs
    ensure_table(conn)
    client = FakeClient({1: (ITEMS, 2)})
    _run("incremental", ["20260628"], client, conn, watermark_from="20260701000000")

    cur = conn.cursor()
    cur.execute("SELECT watermark_to FROM sync_runs ORDER BY id DESC LIMIT 1")
    assert cur.fetchone()[0] == "20260701000000"


def test_watermark_takes_the_newest_modified_time_seen(seed_refs):
    conn = seed_refs
    ensure_table(conn)
    client = FakeClient({1: (ITEMS, 2)})
    _run("incremental", ["20260626"], client, conn, watermark_from="20260626183808")

    cur = conn.cursor()
    cur.execute("SELECT watermark_to FROM sync_runs ORDER BY id DESC LIMIT 1")
    assert cur.fetchone()[0] == "20260627043000"


def test_incremental_requests_one_call_per_day(seed_refs):
    conn = seed_refs
    ensure_table(conn)
    client = FakeClient({})
    _run("incremental", ["20260701", "20260702", "20260703"], client, conn)

    assert [mt for _page, mt in client.calls] == ["20260701", "20260702", "20260703"]
