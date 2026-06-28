from __future__ import annotations

from datetime import datetime

from pictrip_data.db import connect
from pictrip_data.kto.client import KtoClient
from pictrip_data.kto.schemas import KtoSpot
from pictrip_data.sync.audit import last_success_watermark, record_run
from pictrip_data.sync.refcodes import load_ref_codes
from pictrip_data.sync.upsert import upsert_spots


def watermark_param(wm: datetime | None) -> str | None:
    return wm.strftime("%Y%m%d") if wm is not None else None


def _run(
    mode: str,
    modifiedtime: str | None,
    client: KtoClient,
    conn,
    watermark_from: datetime | None = None,
) -> None:
    refs = load_ref_codes(conn)
    with record_run(conn, mode) as c:
        c["watermark_from"] = watermark_from
        max_seen: datetime | None = None
        page = 1
        while True:
            items, _total = client.area_based_sync_list(page=page, modifiedtime=modifiedtime)
            c["api_calls"] += 1
            if not items:
                break
            spots = [KtoSpot.from_kto(x) for x in items]
            c["fetched"] += len(spots)
            upsert_spots(conn, spots, refs, c)
            conn.commit()
            for s in spots:
                if s.modified_time and (max_seen is None or s.modified_time > max_seen):
                    max_seen = s.modified_time
            page += 1
        c["watermark_to"] = max_seen


def sync_daily(mode: str = "daily", client: KtoClient | None = None, conn=None) -> None:
    owns_client = client is None
    owns_conn = conn is None
    client = client or KtoClient()
    if owns_conn:
        with connect() as conn:
            wm = last_success_watermark(conn)
            _run(mode, watermark_param(wm), client, conn, watermark_from=wm)
    else:
        wm = last_success_watermark(conn)
        _run(mode, watermark_param(wm), client, conn, watermark_from=wm)
    if owns_client:
        client.close()


def sync_full(client: KtoClient | None = None, conn=None) -> None:
    """Full reconcile — no modifiedtime filter (~685 pages; quota-aware, weekly)."""
    owns_client = client is None
    client = client or KtoClient()
    if conn is None:
        with connect() as conn:
            _run("full", None, client, conn)
    else:
        _run("full", None, client, conn)
    if owns_client:
        client.close()
