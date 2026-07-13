import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from pictrip_data.overseas.wikidata import USER_AGENT, _is_transient

WIKIDATA_API = "https://www.wikidata.org/w/api.php"
KO_WIKI_API = "https://ko.wikipedia.org/w/api.php"
_QID_BATCH = 50
_TITLE_BATCH = 20
MAX_CHARS = 500


def parse_sitelinks(payload: dict) -> dict[str, str]:
    titles: dict[str, str] = {}
    for qid, entity in payload.get("entities", {}).items():
        title = entity.get("sitelinks", {}).get("kowiki", {}).get("title")
        if title:
            titles[qid] = title
    return titles


def parse_extracts(payload: dict) -> tuple[dict[str, str], dict[str, str]]:
    query = payload.get("query", {})
    alias: dict[str, str] = {}
    for hop in query.get("normalized", []):
        alias[hop["from"]] = hop["to"]
    for hop in query.get("redirects", []):
        alias[hop["from"]] = hop["to"]
    extracts: dict[str, str] = {}
    for page in query.get("pages", {}).values():
        title, extract = page.get("title"), page.get("extract")
        if title and extract:
            extracts[title] = extract
    return extracts, alias


def _resolve(title: str, alias: dict[str, str]) -> str:
    seen = set()
    while title in alias and title not in seen:
        seen.add(title)
        title = alias[title]
    return title


def clean_extract(text: str, max_chars: int = MAX_CHARS) -> str | None:
    first = " ".join(text.strip().split("\n", 1)[0].split())
    if not first:
        return None
    if len(first) <= max_chars:
        return first
    cut = first[:max_chars]
    end = max(cut.rfind("다. "), cut.rfind(". "))
    if end >= max_chars // 2:
        return cut[: end + 2].strip()
    space = cut.rfind(" ")
    return (cut[:space] if space > 0 else cut).rstrip() + "…"


class WikipediaClient:
    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(
            timeout=httpx.Timeout(30.0, connect=5.0), headers={"User-Agent": USER_AGENT}
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception(_is_transient),
        reraise=True,
    )
    def _sitelinks_call(self, qids: list[str]) -> dict:
        resp = self._client.get(
            WIKIDATA_API,
            params={
                "action": "wbgetentities",
                "format": "json",
                "props": "sitelinks",
                "sitefilter": "kowiki",
                "ids": "|".join(qids),
            },
        )
        resp.raise_for_status()
        return resp.json()

    def _sitelinks(self, qids: list[str]) -> dict[str, str]:
        payload = self._sitelinks_call(qids)
        if "error" not in payload:
            return parse_sitelinks(payload)
        if len(qids) <= 1:
            return {}
        mid = len(qids) // 2
        titles = self._sitelinks(qids[:mid])
        titles.update(self._sitelinks(qids[mid:]))
        return titles

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception(_is_transient),
        reraise=True,
    )
    def _extracts(self, titles: list[str]) -> tuple[dict[str, str], dict[str, str]]:
        resp = self._client.get(
            KO_WIKI_API,
            params={
                "action": "query",
                "format": "json",
                "prop": "extracts",
                "exintro": 1,
                "explaintext": 1,
                "exlimit": "max",
                "redirects": 1,
                "titles": "|".join(titles),
            },
        )
        resp.raise_for_status()
        return parse_extracts(resp.json())

    def fetch_descriptions(self, qids: list[str]) -> dict[str, str]:
        out: dict[str, str] = {}
        for i in range(0, len(qids), _QID_BATCH):
            title_by_qid = self._sitelinks(qids[i : i + _QID_BATCH])
            if not title_by_qid:
                continue
            titles = list(title_by_qid.values())
            extracts: dict[str, str] = {}
            alias: dict[str, str] = {}
            for j in range(0, len(titles), _TITLE_BATCH):
                got, hops = self._extracts(titles[j : j + _TITLE_BATCH])
                extracts.update(got)
                alias.update(hops)
            for qid, title in title_by_qid.items():
                raw = extracts.get(_resolve(title, alias))
                desc = clean_extract(raw) if raw else None
                if desc:
                    out[qid] = desc
        return out
