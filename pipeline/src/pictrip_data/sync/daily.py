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
MAX_CATCHUP_MONTHS = 12
"""한 달 질의는 실측 ~4,851건 = 약 49페이지, sync-full 은 68,935건 = 690페이지다.
12개월(≈588페이지)까지는 월 질의가 싸고, 그 너머는 전량이 낫다."""
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


def month_range(start: date, today: date) -> list[str]:
    """modifiedtime 은 프리픽스 필터라 'YYYYMM' 으로 그 달 전체를 한 번에 받는다.

    2026-08-22 라이브 실측: 20260701→72건, 202607→4,851건, 2026→37,223건,
    필터없음→68,935건.
    """
    out: list[str] = []
    year, month = start.year, start.month
    while (year, month) <= (today.year, today.month):
        out.append(f"{year}{month:02d}")
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return out


def sync_dates(wm: str | None, today: date | None = None) -> list[str | None]:
    today = today or datetime.now(_KST).date()
    start = watermark_param(wm)
    if start is None:
        return [None]
    day = min(datetime.strptime(start, "%Y%m%d").date(), today)
    gap = (today - day).days
    if gap > MAX_CATCHUP_DAYS:
        months = month_range(day, today)
        if len(months) > MAX_CATCHUP_MONTHS:
            raise WatermarkTooOld(
                f"watermark {start} 이 {MAX_CATCHUP_MONTHS}개월보다 오래됐다 — "
                "월 질의로도 sync-full 보다 비싸다"
            )
        return list(months)
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
    last = next((m for m in reversed(modifiedtimes) if m), None)
    if last:
        candidates.append(_stamp(last))
    return max(candidates) if candidates else None


def _stamp(modifiedtime: str) -> str:
    """월 질의('202608')도 14자리 워터마크로 편다 — '20260800' 이 되면 다음 실행이
    strptime 에서 죽는다."""
    day = modifiedtime if len(modifiedtime) == 8 else f"{modifiedtime}01"
    return f"{day}000000"


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
