import re
from dataclasses import dataclass
from urllib.parse import quote

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from pictrip_data.overseas.wikidata import USER_AGENT, _is_transient

API = "https://commons.wikimedia.org/w/api.php"
_TAG = re.compile(r"<[^>]+>")
_BATCH = 50


@dataclass(frozen=True)
class Credit:
    author: str | None
    license: str | None
    license_url: str | None


def thumb_url(filename: str) -> str:
    return f"https://commons.wikimedia.org/wiki/Special:FilePath/{quote(filename)}?width=800"


def source_url(filename: str) -> str:
    return f"https://commons.wikimedia.org/wiki/File:{quote(filename)}"


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    text = _TAG.sub("", value).strip()
    return text or None


def parse_credits(payload: dict) -> dict[str, Credit]:
    credits: dict[str, Credit] = {}
    for page in payload.get("query", {}).get("pages", {}).values():
        info = page.get("imageinfo")
        if not info:
            continue
        meta = info[0].get("extmetadata", {})
        name = page["title"].removeprefix("File:")
        credits[name] = Credit(
            author=_clean(meta.get("Artist", {}).get("value")),
            license=_clean(meta.get("LicenseShortName", {}).get("value")),
            license_url=_clean(meta.get("LicenseUrl", {}).get("value")),
        )
    return credits


class CommonsClient:
    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(
            timeout=httpx.Timeout(30.0, connect=5.0), headers={"User-Agent": USER_AGENT}
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8),
           retry=retry_if_exception(_is_transient), reraise=True)
    def _call(self, titles: list[str]) -> dict:
        resp = self._client.get(API, params={
            "action": "query", "format": "json", "prop": "imageinfo",
            "iiprop": "extmetadata", "titles": "|".join(titles),
        })
        resp.raise_for_status()
        return resp.json()

    def fetch_credits(self, filenames: list[str]) -> dict[str, Credit]:
        credits: dict[str, Credit] = {}
        for i in range(0, len(filenames), _BATCH):
            batch = [f"File:{n}" for n in filenames[i : i + _BATCH]]
            credits.update(parse_credits(self._call(batch)))
        return credits
