from dataclasses import dataclass
from urllib.parse import unquote

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from pictrip_data.overseas.countries import Country

SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
USER_AGENT = "PicTripDataBot/1.0 (https://pictrip.org; dev@pictrip.org)"
MIN_SITELINKS = 10
_CLASS_QIDS = ["Q570116", "Q33506", "Q16560", "Q23413", "Q4989906", "Q839954", "Q8502"]
_SETTLEMENT_QIDS = [
    "Q515",
    "Q1549591",
    "Q200250",
    "Q174844",
    "Q134626",
    "Q902814",
    "Q3957",
    "Q42744322",
    "Q133997300",
    "Q6882870",
    "Q4946461",
    "Q990488",
    "Q12350930",
]
_RUINS_EXEMPT_QID = "Q839954"
_SETTLEMENT_BATCH = 300

_QUERY_TMPL = """SELECT DISTINCT ?item ?ko ?en ?desc ?img ?links ?lat ?lng WHERE {{
  ?item wdt:P17 wd:{country} ; wdt:P18 ?img ; wikibase:sitelinks ?links ; rdfs:label ?ko .
  FILTER(LANG(?ko) = "ko") FILTER(?links >= {min_links})
  {class_union}
  OPTIONAL {{ ?item schema:description ?desc . FILTER(LANG(?desc) = "ko") }}
  OPTIONAL {{ ?item rdfs:label ?en . FILTER(LANG(?en) = "en") }}
  OPTIONAL {{ ?item p:P625/psv:P625 [ wikibase:geoLatitude ?lat ; wikibase:geoLongitude ?lng ] . }}
}}"""

_SETTLEMENT_QUERY_TMPL = """SELECT DISTINCT ?item WHERE {{
  VALUES ?item {{ {items} }}
  VALUES ?settlement {{ {settlements} }}
  ?item wdt:P31 ?settlement .
  FILTER NOT EXISTS {{ ?item wdt:P31/wdt:P279* wd:{exempt} . }}
}}"""


@dataclass(frozen=True)
class RawSpot:
    wikidata_id: str
    name_ko: str
    name_en: str | None
    description_ko: str | None
    image_filename: str
    fame_score: int
    lat: float | None
    lng: float | None
    country: Country


def build_query(country: Country) -> str:
    union = "\n  UNION ".join(f"{{ ?item wdt:P31/wdt:P279* wd:{q} . }}" for q in _CLASS_QIDS)
    return _QUERY_TMPL.format(country=country.qid, min_links=MIN_SITELINKS, class_union=union)


def build_settlement_query(qids: list[str]) -> str:
    return _SETTLEMENT_QUERY_TMPL.format(
        items=" ".join(f"wd:{q}" for q in qids),
        settlements=" ".join(f"wd:{q}" for q in _SETTLEMENT_QIDS),
        exempt=_RUINS_EXEMPT_QID,
    )


def _filename_from_image_url(url: str) -> str:
    return unquote(url.rsplit("/", 1)[-1])


def parse_bindings(bindings: list[dict], country: Country) -> list[RawSpot]:
    seen: dict[str, RawSpot] = {}
    for b in bindings:
        qid = b["item"]["value"].rsplit("/", 1)[-1]
        if qid in seen:
            continue
        seen[qid] = RawSpot(
            wikidata_id=qid,
            name_ko=b["ko"]["value"],
            name_en=b.get("en", {}).get("value"),
            description_ko=b.get("desc", {}).get("value"),
            image_filename=_filename_from_image_url(b["img"]["value"]),
            fame_score=int(b["links"]["value"]),
            lat=float(b["lat"]["value"]) if "lat" in b else None,
            lng=float(b["lng"]["value"]) if "lng" in b else None,
            country=country,
        )
    return list(seen.values())


def _is_transient(exc: BaseException) -> bool:
    if isinstance(exc, httpx.RequestError):
        return True
    return isinstance(exc, httpx.HTTPStatusError) and (
        exc.response.status_code == 429 or exc.response.status_code >= 500
    )


class WikidataClient:
    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(
            timeout=httpx.Timeout(90.0, connect=5.0), headers={"User-Agent": USER_AGENT}
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        retry=retry_if_exception(_is_transient),
        reraise=True,
    )
    def _query(self, query: str) -> list[dict]:
        resp = self._client.post(SPARQL_ENDPOINT, data={"query": query, "format": "json"})
        resp.raise_for_status()
        return list(resp.json()["results"]["bindings"])

    def fetch_country(self, country: Country) -> list[RawSpot]:
        spots = parse_bindings(self._query(build_query(country)), country)
        settlements = self.fetch_settlement_qids([s.wikidata_id for s in spots])
        return [s for s in spots if s.wikidata_id not in settlements]

    def fetch_settlement_qids(self, qids: list[str]) -> set[str]:
        found: set[str] = set()
        for start in range(0, len(qids), _SETTLEMENT_BATCH):
            batch = qids[start : start + _SETTLEMENT_BATCH]
            for b in self._query(build_settlement_query(batch)):
                found.add(b["item"]["value"].rsplit("/", 1)[-1])
        return found
