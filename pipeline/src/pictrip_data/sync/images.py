from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit

import httpx
import psycopg

from pictrip_data.db import connect
from pictrip_data.sync.audit import record_run

KTO_IMAGE_HOST = "tong.visitkorea.or.kr"
_HIRES = "_image1_1"
_MID = "_image2_1"
_USER_AGENT = "PicTripDataBot/1.0 (+https://pictrip.org)"
_TIMEOUT = 10.0
_WORKERS = 6
_COMMIT_EVERY = 500

ALIVE = "alive"
DEAD = "dead"
UNKNOWN = "unknown"

_SELECT = (
    "SELECT content_id, first_image_url FROM spots "
    "WHERE show_flag = 1 AND first_image_url IS NOT NULL AND first_image_url <> '' "
    "ORDER BY content_id"
)
_REWRITE = (
    "UPDATE spots SET first_image_url = %s, synced_at = now() "
    "WHERE content_id = %s AND first_image_url = %s"
)
_CLEAR = (
    "UPDATE spots SET first_image_url = NULL, synced_at = now() "
    "WHERE content_id = %s AND first_image_url = %s"
)


def mid_size_url(url: str) -> str | None:
    if urlsplit(url).hostname != KTO_IMAGE_HOST or _HIRES not in url:
        return None
    return url.replace(_HIRES, _MID)


def _https(url: str) -> str:
    return "https://" + url.removeprefix("http://") if url.startswith("http://") else url


def probe(client: httpx.Client, url: str) -> str:
    try:
        response = client.get(_https(url), headers={"Range": "bytes=0-0"})
    except httpx.HTTPError:
        return UNKNOWN
    if response.status_code in (404, 410):
        return DEAD
    if response.status_code in (200, 206):
        content_type = response.headers.get("content-type", "")
        return ALIVE if content_type.lower().startswith("image/") else UNKNOWN
    return UNKNOWN


def _resolve(client: httpx.Client, url: str) -> tuple[str, str | None, int]:
    state = probe(client, url)
    if state != DEAD:
        return state, None, 1
    mid = mid_size_url(url)
    if mid is None:
        return DEAD, None, 1
    mid_state = probe(client, mid)
    if mid_state == ALIVE:
        return DEAD, mid, 2
    if mid_state == UNKNOWN:
        return UNKNOWN, None, 2
    return DEAD, None, 2


def _validate(
    conn: psycopg.Connection,
    client: httpx.Client,
    counters: dict,
    dry_run: bool,
    limit: int | None,
) -> None:
    cur = conn.cursor()
    if limit is not None:
        cur.execute(_SELECT + " LIMIT %s", (limit,))
    else:
        cur.execute(_SELECT)
    rows = cur.fetchall()
    with ThreadPoolExecutor(max_workers=_WORKERS) as pool:
        for start in range(0, len(rows), _COMMIT_EVERY):
            chunk = rows[start : start + _COMMIT_EVERY]
            resolved = list(pool.map(lambda row: _resolve(client, row[1]), chunk))
            for (content_id, url), (state, replacement, probes) in zip(chunk, resolved):
                counters["api_calls"] += probes
                counters["fetched"] += 1
                if state != DEAD:
                    if state == UNKNOWN:
                        counters["skipped"] += 1
                    continue
                if replacement is not None:
                    counters["updated"] += 1
                    if not dry_run:
                        cur.execute(_REWRITE, (replacement, content_id, url))
                else:
                    counters["soft_deleted"] += 1
                    if not dry_run:
                        cur.execute(_CLEAR, (content_id, url))
            if not dry_run:
                conn.commit()


def _summary(counters: dict) -> dict[str, int]:
    return {
        "probed": counters["fetched"],
        "rewritten": counters["updated"],
        "cleared": counters["soft_deleted"],
        "unknown": counters["skipped"],
        "probes": counters["api_calls"],
    }


def _run(
    conn: psycopg.Connection, client: httpx.Client, dry_run: bool, limit: int | None
) -> dict[str, int]:
    if dry_run:
        counters = {"api_calls": 0, "fetched": 0, "updated": 0, "soft_deleted": 0, "skipped": 0}
        _validate(conn, client, counters, True, limit)
        return _summary(counters)
    with record_run(conn, "validate-images") as counters:
        _validate(conn, client, counters, False, limit)
    return _summary(counters)


def validate_images(
    conn: psycopg.Connection | None = None,
    client: httpx.Client | None = None,
    dry_run: bool = False,
    limit: int | None = None,
) -> dict[str, int]:
    owns_client = client is None
    client = client or httpx.Client(
        timeout=_TIMEOUT, follow_redirects=True, headers={"User-Agent": _USER_AGENT}
    )
    try:
        if conn is None:
            with connect() as owned:
                return _run(owned, client, dry_run, limit)
        return _run(conn, client, dry_run, limit)
    finally:
        if owns_client:
            client.close()
