import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from pictrip_data.kto.client import KtoServiceError, _body
from pictrip_data.sync.audit import ensure_table
from pictrip_data.sync.daily import (
    MAX_CATCHUP_DAYS,
    PartialFullSync,
    TruncatedPageLoop,
    WatermarkTooOld,
    _advanced_watermark,
    month_range,
    _run,
    sync_daily,
    sync_dates,
    sync_full,
    watermark_param,
)

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "sync_list_response.json").read_text())
ITEMS = FIXTURE["response"]["body"]["items"]["item"]


class FakeClient:
    """실제 API 처럼 totalCount 를 모든 페이지에서 같은 값으로 준다.

    total 을 따로 넘기면 "totalCount 는 큰데 items 가 먼저 끊기는" 잘린 응답이 된다.
    """

    def __init__(self, pages, total=None):
        self.pages = pages
        self.total = total if total is not None else sum(len(i) for i, _ in pages.values())
        self.calls = []

    def area_based_sync_list(self, *, page, rows=100, modifiedtime=None):
        self.calls.append((page, modifiedtime))
        items, _ = self.pages.get(page, ([], 0))
        return items, self.total


def test_watermark_param_slices_date():
    assert watermark_param("20260627043000") == "20260627"
    assert watermark_param(None) is None
    assert watermark_param("") is None


def test_truncated_page_loop_stops_before_the_watermark_advances(seed_refs):
    conn = seed_refs
    ensure_table(conn)
    client = FakeClient({1: (ITEMS, 130)}, total=130)

    with pytest.raises(TruncatedPageLoop):
        _run("incremental", ["20260701"], client, conn, watermark_from="20260630000000")

    cur = conn.cursor()
    cur.execute("SELECT status, watermark_to FROM sync_runs ORDER BY id DESC LIMIT 1")
    status, watermark_to = cur.fetchone()
    assert status == "error"
    assert watermark_to is None


def test_total_count_stops_the_loop_without_an_extra_empty_page(seed_refs):
    conn = seed_refs
    ensure_table(conn)
    client = FakeClient({1: (ITEMS, 2)})
    _run("incremental", ["20260701"], client, conn)

    assert client.calls == [(1, "20260701")]


def test_paging_continues_until_total_count_is_reached(seed_refs):
    conn = seed_refs
    ensure_table(conn)
    client = FakeClient({1: (ITEMS[:1], 2), 2: (ITEMS[1:], 2)})
    _run("incremental", ["20260701"], client, conn)

    assert [page for page, _mt in client.calls] == [1, 2]
    cur = conn.cursor()
    cur.execute("SELECT status, fetched FROM sync_runs ORDER BY id DESC LIMIT 1")
    assert cur.fetchone() == ("success", 2)


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


def test_a_half_year_gap_is_recoverable_by_month_queries():
    """예전에는 여기서 WatermarkTooOld 를 던지고 sync-full 을 기다렸다."""
    assert sync_dates("20260101000000", date(2026, 6, 29)) == [
        "202601",
        "202602",
        "202603",
        "202604",
        "202605",
        "202606",
    ]


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


def test_sync_dates_clamps_a_future_watermark():
    assert sync_dates("20260930120000", date(2026, 6, 29)) == ["20260629"]


def test_kto_error_envelope_raises_instead_of_looking_empty():
    payload = {
        "response": {
            "header": {"resultCode": "22", "resultMsg": "LIMITED NUMBER OF SERVICE REQUESTS"},
            "body": {},
        }
    }
    with pytest.raises(KtoServiceError):
        _body(payload, "areaBasedSyncList2")


def test_kto_ok_envelope_returns_body():
    payload = {"response": {"header": {"resultCode": "0000"}, "body": {"totalCount": 3}}}
    assert _body(payload, "areaBasedSyncList2") == {"totalCount": 3}


def test_short_gap_still_walks_day_by_day():
    dates = sync_dates("20260818000000", date(2026, 8, 22))
    assert dates == ["20260818", "20260819", "20260820", "20260821", "20260822"]


def test_the_day_loop_holds_right_up_to_the_cliff():
    edge = date(2026, 8, 22) - timedelta(days=MAX_CATCHUP_DAYS)
    dates = sync_dates(f"{edge:%Y%m%d}000000", date(2026, 8, 22))
    assert len(dates) == MAX_CATCHUP_DAYS + 1
    assert all(len(d) == 8 for d in dates)


def test_a_long_gap_switches_to_month_queries_instead_of_failing():
    """예전에는 61일이면 WatermarkTooOld 로 sync-full(690페이지)에 넘겼다."""
    dates = sync_dates("20260601000000", date(2026, 8, 22))
    assert dates == ["202606", "202607", "202608"]


def test_month_range_crosses_the_year_boundary():
    assert month_range(date(2025, 11, 3), date(2026, 2, 9)) == [
        "202511",
        "202512",
        "202601",
        "202602",
    ]


def test_beyond_a_year_still_defers_to_sync_full():
    with pytest.raises(WatermarkTooOld):
        sync_dates("20240101000000", date(2026, 8, 22))


def test_month_watermark_stays_parseable_by_the_next_run():
    """'202608' 이 그대로 워터마크가 되면 [:8] 이 '20260800' 이라 다음 실행이 죽는다."""
    wm = _advanced_watermark(None, None, ["202606", "202607", "202608"])
    assert wm == "20260801000000"
    assert sync_dates(wm, date(2026, 8, 22))[0] == "20260801"
