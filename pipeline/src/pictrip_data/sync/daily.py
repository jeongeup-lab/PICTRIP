from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from pictrip_data.db import connect
from pictrip_data.kto.client import KtoClient
from pictrip_data.kto.schemas import KtoSpot
from pictrip_data.sync.audit import last_success_watermark, record_run
from pictrip_data.sync.refcodes import load_ref_codes
from pictrip_data.sync.upsert import upsert_spots


MIN_SEEN_RATIO = 0.5
MAX_CATCHUP_DAYS = 60
MAX_PAGES = 1000
_PROGRESS_EVERY = 50
_KST = ZoneInfo("Asia/Seoul")


class PartialFullSync(RuntimeError):
    pass


class WatermarkTooOld(RuntimeError):
    pass


class TruncatedPageLoop(RuntimeError):
    """resultCode 는 정상인데 items 만 짧게 오는 응답을 워터마크 전진 전에 끊는다.

    modifiedtime 은 날짜 등가 필터라 한 번 건너뛴 날짜는 영영 다시 조회되지 않는다.
    빈 페이지로 루프가 끊겼는데 totalCount 에 못 미치면 그게 유실이다.
    """


def watermark_param(wm: str | None) -> str | None:
    return wm[:8] if wm else None


def sync_dates(wm: str | None, today: date | None = None) -> list[str | None]:
    today = today or datetime.now(_KST).date()
    start = watermark_param(wm)
    if start is None:
        return [None]
    day = min(datetime.strptime(start, "%Y%m%d").date(), today)
    if (today - day).days > MAX_CATCHUP_DAYS:
        raise WatermarkTooOld(
            f"watermark {start} 이 {MAX_CATCHUP_DAYS}일보다 오래됐다 — sync-full 로 복구할 것"
        )
    out: list[str | None] = []
    while day <= today:
        out.append(day.strftime("%Y%m%d"))
        day += timedelta(days=1)
    return out


def soft_delete_unseen(conn, seen: set[str]) -> int:
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM spots WHERE show_flag = 1")
    visible = cur.fetchone()[0]
    if visible and len(seen) < visible * MIN_SEEN_RATIO:
        raise PartialFullSync(
            f"full sync saw {len(seen)} of {visible} visible spots "
            f"(< {MIN_SEEN_RATIO:.0%}) — refusing to soft-delete"
        )
    cur.execute(
        "CREATE TEMP TABLE seen_content_ids (content_id varchar(32) PRIMARY KEY) ON COMMIT DROP"
    )
    with cur.copy("COPY seen_content_ids (content_id) FROM STDIN") as copy:
        for content_id in seen:
            copy.write_row((content_id,))
    cur.execute(
        "UPDATE spots SET show_flag = 0, synced_at = now() "
        "WHERE show_flag = 1 AND NOT EXISTS ("
        "SELECT 1 FROM seen_content_ids s WHERE s.content_id = spots.content_id)"
    )
    return cur.rowcount


def _sync_one_date(
    modifiedtime: str | None,
    client: KtoClient,
    conn,
    refs,
    c: dict,
    seen: set[str],
) -> datetime | None:
    label = modifiedtime or "all"
    max_seen: datetime | None = None
    page = 1
    fetched = 0
    total = 0
    while True:
        if page > MAX_PAGES:
            raise TruncatedPageLoop(f"{label}: {MAX_PAGES} 페이지 상한을 넘었다")
        items, page_total = client.area_based_sync_list(page=page, modifiedtime=modifiedtime)
        c["api_calls"] += 1
        if page == 1:
            total = page_total
        if not items:
            if fetched < total:
                raise TruncatedPageLoop(f"{label}: {fetched}/{total} 건에서 응답이 끊겼다")
            break
        spots = [KtoSpot.from_kto(x) for x in items]
        c["fetched"] += len(spots)
        fetched += len(spots)
        upsert_spots(conn, spots, refs, c)
        conn.commit()
        for s in spots:
            seen.add(s.content_id)
            if s.modified_time and (max_seen is None or s.modified_time > max_seen):
                max_seen = s.modified_time
        if total and fetched >= total:
            break
        if page % _PROGRESS_EVERY == 0:
            print(f"[sync] {label} page={page} fetched={fetched}/{total}", flush=True)
        page += 1
    print(f"[sync] {label} done fetched={fetched}/{total} pages={page}", flush=True)
    return max_seen


def _run(
    mode: str,
    modifiedtimes: list[str | None],
    client: KtoClient,
    conn,
    watermark_from: str | None = None,
) -> dict:
    refs = load_ref_codes(conn)
    with record_run(conn, mode) as c:
        c["watermark_from"] = watermark_from
        max_seen: datetime | None = None
        seen: set[str] = set()
        for modifiedtime in modifiedtimes:
            date_max = _sync_one_date(modifiedtime, client, conn, refs, c, seen)
            if date_max and (max_seen is None or date_max > max_seen):
                max_seen = date_max
        if mode == "full" and seen:
            c["soft_deleted"] += soft_delete_unseen(conn, seen)
            conn.commit()
        c["watermark_to"] = _advanced_watermark(watermark_from, max_seen, modifiedtimes)
    return c


def _advanced_watermark(
    watermark_from: str | None, max_seen: datetime | None, modifiedtimes: list[str | None]
) -> str | None:
    candidates = [w for w in (watermark_from,) if w]
    if max_seen is not None:
        candidates.append(max_seen.strftime("%Y%m%d%H%M%S"))
    last_day = next((m for m in reversed(modifiedtimes) if m), None)
    if last_day:
        candidates.append(f"{last_day}000000")
    return max(candidates) if candidates else None


def sync_daily(mode: str = "incremental", client: KtoClient | None = None, conn=None) -> dict:
    owns_client = client is None
    owns_conn = conn is None
    client = client or KtoClient()
    try:
        if owns_conn:
            with connect() as conn:
                wm = last_success_watermark(conn)
                return _run(mode, sync_dates(wm), client, conn, watermark_from=wm)
        wm = last_success_watermark(conn)
        return _run(mode, sync_dates(wm), client, conn, watermark_from=wm)
    finally:
        if owns_client:
            client.close()


def sync_full(client: KtoClient | None = None, conn=None) -> dict:
    owns_client = client is None
    client = client or KtoClient()
    try:
        if conn is None:
            with connect() as conn:
                return _run("full", [None], client, conn)
        return _run("full", [None], client, conn)
    finally:
        if owns_client:
            client.close()
