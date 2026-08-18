from pictrip_data.overseas.wikipedia import WikipediaClient

MIN_DESC_CHARS = 80

_SELECT_NODESC = (
    "SELECT id, wikidata_id FROM overseas_spots "
    "WHERE coalesce(length(description_ko), 0) < %(min_chars)s ORDER BY id"
)
_UPDATE_DESC = (
    "UPDATE overseas_spots SET description_ko = %(desc)s, updated_at = now() WHERE id = %(id)s"
)


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
    counters = fill_missing_descriptions(wikipedia, conn)
    if dry_run:
        conn.rollback()
    else:
        conn.commit()
    return counters


def fill_missing_descriptions(wikipedia, conn, limit: int | None = None) -> dict[str, int]:
    counters = {"scanned": 0, "updated": 0, "skipped": 0}
    sql = _SELECT_NODESC + (" LIMIT %(lim)s" if limit else "")
    with conn.cursor() as cur:
        cur.execute(sql, {"min_chars": MIN_DESC_CHARS, "lim": limit})
        rows = cur.fetchall()
    ids_by_qid: dict[str, list[int]] = {}
    for oid, qid in rows:
        counters["scanned"] += 1
        ids_by_qid.setdefault(qid, []).append(oid)
    if not ids_by_qid:
        return counters
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
    return counters
