from urllib.parse import unquote

from pictrip_data.overseas.commons import CommonsClient
from pictrip_data.overseas.wikipedia import WikipediaClient

_FILE_PREFIX = "https://commons.wikimedia.org/wiki/File:"
_SELECT = (
    "SELECT id, image_source_url FROM overseas_spots "
    "WHERE image_url LIKE 'https://commons.wikimedia.org/wiki/Special:FilePath/%'"
)
_UPDATE = "UPDATE overseas_spots SET image_url = %(url)s, updated_at = now() WHERE id = %(id)s"

_SELECT_NODESC = (
    "SELECT id, wikidata_id FROM overseas_spots WHERE description_ko IS NULL OR description_ko = ''"
)
_UPDATE_DESC = (
    "UPDATE overseas_spots SET description_ko = %(desc)s, updated_at = now() WHERE id = %(id)s"
)


def _filename(source_url: str | None) -> str | None:
    if not source_url or not source_url.startswith(_FILE_PREFIX):
        return None
    return unquote(source_url.removeprefix(_FILE_PREFIX))


def backfill_overseas_thumbs(*, commons=None, conn=None, dry_run: bool = False) -> dict[str, int]:
    commons = commons or CommonsClient()
    if conn is not None:
        return _run(commons, conn, dry_run)
    from pictrip_data.db import connect

    with connect() as owned:
        return _run(commons, owned, dry_run)


def _run(commons, conn, dry_run: bool) -> dict[str, int]:
    counters = {"scanned": 0, "updated": 0, "skipped": 0}
    with conn.cursor() as cur:
        cur.execute(_SELECT)
        rows = cur.fetchall()
    ids_by_file: dict[str, list[int]] = {}
    for oid, source_url in rows:
        counters["scanned"] += 1
        name = _filename(source_url)
        if name is None:
            counters["skipped"] += 1
            continue
        ids_by_file.setdefault(name, []).append(oid)
    credits = commons.fetch_credits(list(ids_by_file))
    with conn.cursor() as cur:
        for name, ids in ids_by_file.items():
            credit = credits.get(name)
            thumb = credit.thumb if credit else None
            if not thumb:
                counters["skipped"] += len(ids)
                continue
            for oid in ids:
                cur.execute(_UPDATE, {"url": thumb, "id": oid})
                counters["updated"] += 1
    if dry_run:
        conn.rollback()
    else:
        conn.commit()
    return counters


def backfill_overseas_descriptions(
    *, wikipedia=None, conn=None, dry_run: bool = False
) -> dict[str, int]:
    wikipedia = wikipedia or WikipediaClient()
    if conn is not None:
        return _run_descriptions(wikipedia, conn, dry_run)
    from pictrip_data.db import connect

    with connect() as owned:
        return _run_descriptions(wikipedia, owned, dry_run)


def _run_descriptions(wikipedia, conn, dry_run: bool) -> dict[str, int]:
    counters = {"scanned": 0, "updated": 0, "skipped": 0}
    with conn.cursor() as cur:
        cur.execute(_SELECT_NODESC)
        rows = cur.fetchall()
    ids_by_qid: dict[str, list[int]] = {}
    for oid, qid in rows:
        counters["scanned"] += 1
        ids_by_qid.setdefault(qid, []).append(oid)
    descriptions = wikipedia.fetch_descriptions(list(ids_by_qid))
    with conn.cursor() as cur:
        for qid, ids in ids_by_qid.items():
            desc = descriptions.get(qid)
            if not desc:
                counters["skipped"] += len(ids)
                continue
            for oid in ids:
                cur.execute(_UPDATE_DESC, {"desc": desc, "id": oid})
                counters["updated"] += 1
    if dry_run:
        conn.rollback()
    else:
        conn.commit()
    return counters
