import json
from pathlib import Path

import httpx

from pictrip_data.kto.client import KtoClient

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "sync_list_response.json").read_text())


def _client(handler):
    transport = httpx.MockTransport(handler)
    return KtoClient(client=httpx.Client(transport=transport))


def test_returns_items_and_total():
    def handler(request: httpx.Request) -> httpx.Response:
        assert "areaBasedSyncList2" in str(request.url)
        assert request.url.params.get("_type") == "json"
        assert request.url.params.get("showflag") is None  # omitted to receive hidden
        assert request.url.params.get("arrange") == "C"
        return httpx.Response(200, json=FIXTURE)

    items, total = _client(handler).area_based_sync_list(page=1)
    assert total == 68433
    assert len(items) == 2
    assert items[0]["contentid"] == "2865520"


def test_passes_modifiedtime_when_given():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["mt"] = request.url.params.get("modifiedtime")
        return httpx.Response(200, json=FIXTURE)

    _client(handler).area_based_sync_list(page=1, modifiedtime="20260627")
    assert seen["mt"] == "20260627"


def test_empty_body_returns_empty_list():
    empty = {"response": {"header": {"resultCode": "0000"}, "body": {"items": "", "totalCount": 0}}}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=empty)

    items, total = _client(handler).area_based_sync_list(page=99)
    assert items == []
    assert total == 0
