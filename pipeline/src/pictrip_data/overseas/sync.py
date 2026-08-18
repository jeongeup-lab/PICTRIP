from pictrip_data.db import connect
from pictrip_data.overseas.backfill import fill_missing_descriptions
from pictrip_data.overseas.commons import CommonsClient
from pictrip_data.overseas.countries import COUNTRIES, Country
from pictrip_data.overseas.upsert import upsert_overseas
from pictrip_data.overseas.wikidata import WikidataClient
from pictrip_data.overseas.wikipedia import WikipediaClient
from pictrip_data.sync.audit import ensure_table, record_run

MAX_FAILED_COUNTRY_RATIO = 1 / 3


class PartialOverseasSync(RuntimeError):
    pass


def sync_overseas(
    *,
    wikidata=None,
    commons=None,
    wikipedia=None,
    conn=None,
    countries: list[Country] | None = None,
    limit: int | None = None,
    dry_run: bool = False,
) -> None:
    wikidata = wikidata or WikidataClient()
    commons = commons or CommonsClient()
    wikipedia = wikipedia or WikipediaClient()
    countries = countries if countries is not None else COUNTRIES
    if conn is not None:
        _run(wikidata, commons, wikipedia, conn, countries, limit, dry_run)
        return
    with connect() as owned:
        _run(wikidata, commons, wikipedia, owned, countries, limit, dry_run)


def _process(wikidata, commons, wikipedia, conn, countries, counters, limit, dry_run) -> None:
    total = 0
    failed: list[str] = []
    for country in countries:
        try:
            spots = wikidata.fetch_country(country)
        except Exception as exc:
            conn.rollback()
            failed.append(f"{country.code}({type(exc).__name__})")
            continue
        counters["api_calls"] += 1
        if limit is not None:
            spots = spots[: max(limit - total, 0)]
        if not spots:
            continue
        credits = commons.fetch_credits([s.image_filename for s in spots])
        counters["api_calls"] += (len(spots) + 49) // 50
        with conn.cursor() as cur:
            for spot in spots:
                inserted = upsert_overseas(cur, spot, credits.get(spot.image_filename))
                counters["inserted" if inserted else "updated"] += 1
        counters["fetched"] += len(spots)
        total += len(spots)
        if not dry_run:
            conn.commit()
        if limit is not None and total >= limit:
            break

    descriptions = fill_missing_descriptions(wikipedia, conn, limit=limit)
    counters["updated"] += descriptions["updated"]
    if not dry_run:
        conn.commit()

    if failed and len(failed) > len(countries) * MAX_FAILED_COUNTRY_RATIO:
        raise PartialOverseasSync(f"{len(failed)}/{len(countries)} 국가 실패: {', '.join(failed)}")


def _run(wikidata, commons, wikipedia, conn, countries, limit, dry_run) -> None:
    ensure_table(conn)
    if dry_run:
        counters = {"api_calls": 0, "fetched": 0, "inserted": 0, "updated": 0}
        try:
            _process(wikidata, commons, wikipedia, conn, countries, counters, limit, dry_run)
        finally:
            conn.rollback()
        return
    with record_run(conn, mode="overseas") as counters:
        _process(wikidata, commons, wikipedia, conn, countries, counters, limit, dry_run)
