"""KTO OpenAPI client (areaBasedSyncList2 etc.)."""

from __future__ import annotations

from typing import Any

import httpx

from pictrip_data.config import settings

BASE_URL = "https://apis.data.go.kr/B551011/KorService2"


class KtoClient:
    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(base_url=BASE_URL, timeout=30)
        self._key = settings.kto_api_key

    def area_based_sync_list(self, *, page: int = 1, rows: int = 100) -> list[dict[str, Any]]:
        """Fetch one page of areaBasedSyncList2.

        TODO: pass serviceKey/_type=json/MobileOS/MobileApp + paging, parse the
        nested response, honor rate limits, return raw item dicts.
        """
        _ = (page, rows, self._key)
        return []
