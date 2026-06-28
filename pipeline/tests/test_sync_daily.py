import json
from pathlib import Path

from pictrip_data.sync.audit import ensure_table
from pictrip_data.sync.daily import sync_daily, watermark_param

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
    # Watermark stored as raw KTO text 'YYYYMMDDHHMMSS'; the filter wants 'YYYYMMDD'.
    assert watermark_param("20260627043000") == "20260627"
    assert watermark_param(None) is None
    assert watermark_param("") is None


def test_sync_daily_pages_until_empty_and_records(seed_refs):
    conn = seed_refs
    ensure_table(conn)
    # page 1 returns the 2 fixture items (content T uses real ids), page 2 empty
    client = FakeClient({1: (ITEMS, 2)})
    sync_daily(mode="daily", client=client, conn=conn)

    cur = conn.cursor()
    cur.execute("SELECT status, fetched FROM sync_runs ORDER BY id DESC LIMIT 1")
    status, fetched = cur.fetchone()
    assert status == "success"
    assert fetched == 2
    # second item (showflag=1) is visible, first (showflag=0) hidden
    cur.execute("SELECT show_flag FROM spots WHERE content_id='3509884'")
    assert cur.fetchone()[0] == 1
    cur.execute("SELECT show_flag FROM spots WHERE content_id='2865520'")
    assert cur.fetchone()[0] == 0
