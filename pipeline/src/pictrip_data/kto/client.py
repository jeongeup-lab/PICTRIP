"""KTO OpenAPI client (areaBasedSyncList2 etc.)."""

from __future__ import annotations

from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from pictrip_data.config import settings

_OPERATION = "areaBasedSyncList2"


def _is_transient(exc: BaseException) -> bool:
    """Retry only on transient errors: connection/timeout problems, HTTP 429,
    and 5xx. A non-transient 4xx (e.g. a bad serviceKey) must raise immediately
    instead of burning retries against the daily quota."""
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        return status == 429 or status >= 500
    return isinstance(exc, httpx.RequestError)


class KtoClient:
    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(
            base_url=settings.kto_base_url_kor,
            timeout=httpx.Timeout(30.0, connect=5.0),
        )

    def close(self) -> None:
        self._client.close()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception(_is_transient),
        reraise=True,
    )
    def area_based_sync_list(
        self, *, page: int, rows: int = 100, modifiedtime: str | None = None
    ) -> tuple[list[dict[str, Any]], int]:
        """One page of the sync list. showflag omitted on purpose so hidden
        (showflag=0) items arrive and can be soft-deleted."""
        params = {
            "serviceKey": settings.kto_api_key,
            "MobileOS": "ETC",
            "MobileApp": settings.kto_mobile_app,
            "_type": "json",
            "arrange": "C",  # by modified date
            "numOfRows": rows,
            "pageNo": page,
        }
        if modifiedtime is not None:
            params["modifiedtime"] = modifiedtime

        url = f"{settings.kto_base_url_kor}/{_OPERATION}"
        resp = self._client.get(url, params=params)
        resp.raise_for_status()
        body = resp.json().get("response", {}).get("body", {})
        total = int(body.get("totalCount") or 0)
        items = body.get("items")
        if not items:
            return [], total
        item = items.get("item", [])
        return (item if isinstance(item, list) else [item]), total
