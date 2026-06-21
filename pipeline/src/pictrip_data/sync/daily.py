"""Daily spots sync from KTO areaBasedSyncList2."""

from __future__ import annotations

from pictrip_data.db import connect
from pictrip_data.sync.audit import record_run
from pictrip_data.sync.upsert import upsert_spots


def sync_daily() -> None:
    """Fetch the watermark window from KTO and upsert spots, auditing the run."""
    with connect() as conn, record_run(conn, mode="daily") as counters:
        # TODO:
        #   1. resolve watermark (last successful run -> now)
        #   2. page through KtoClient.area_based_sync_list(...)
        #   3. upsert_spots(conn, batch, counters)
        #   4. soft-delete rows missing from the sync window (show_flag = 0)
        upsert_spots(conn, rows=[], counters=counters)
