"""GET /v1/map/region — Kakao coord2regioncode reverse-geocode + Redis cache."""

from __future__ import annotations

import re

import pytest
from fakeredis.aioredis import FakeRedis

from app.config import settings
from app.core.redis import get_redis
from app.main import app

# pytest-httpx has no startswith match, so use a regex that ignores the query string.
_KAKAO_URL = re.compile(r"https://dapi\.kakao\.com/v2/local/geo/coord2regioncode\.json.*")


@pytest.fixture(autouse=True)
def _kakao_key(monkeypatch):
    # CI has no .env (empty key → reverse_geocode returns None early); pin a key so behavior is fixed.
    monkeypatch.setattr(settings, "KAKAO_REST_API_KEY", "test-kakao-key")


_DOCS = {
    "documents": [
        {
            "region_type": "B",
            "region_1depth_name": "서울특별시",
            "region_2depth_name": "광진구",
            "region_3depth_name": "화양동",
        },
        {
            "region_type": "H",
            "region_1depth_name": "서울특별시",
            "region_2depth_name": "광진구",
            "region_3depth_name": "화양동",
        },
    ]
}


@pytest.mark.asyncio
async def test_region_prefers_admin_and_builds_label(client, httpx_mock):
    httpx_mock.add_response(url=_KAKAO_URL, json=_DOCS)
    redis = FakeRedis(decode_responses=False)
    app.dependency_overrides[get_redis] = lambda: redis
    try:
        resp = await client.get("/v1/map/region", params={"lat": 37.546, "lng": 127.071})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["sigungu"] == "광진구"
    assert data["dong"] == "화양동"
    assert data["label"] == "광진구 화양동"


@pytest.mark.asyncio
async def test_region_caches_second_call(client, httpx_mock):
    httpx_mock.add_response(url=_KAKAO_URL, json=_DOCS)
    redis = FakeRedis(decode_responses=False)
    app.dependency_overrides[get_redis] = lambda: redis
    try:
        await client.get("/v1/map/region", params={"lat": 37.546, "lng": 127.071})
        await client.get("/v1/map/region", params={"lat": 37.546, "lng": 127.071})
    finally:
        app.dependency_overrides.clear()
    # same grid cell → Kakao called only once
    assert len(httpx_mock.get_requests()) == 1


@pytest.mark.asyncio
async def test_region_returns_null_on_empty(client, httpx_mock):
    httpx_mock.add_response(url=_KAKAO_URL, json={"documents": []})
    redis = FakeRedis(decode_responses=False)
    app.dependency_overrides[get_redis] = lambda: redis
    try:
        resp = await client.get("/v1/map/region", params={"lat": 0.0, "lng": 0.0})
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert resp.json()["data"] is None


class _BrokenRedis:
    """get/set both raise — a dead cache must behave like a miss (#13)."""

    async def get(self, key):
        raise ConnectionError("redis down")

    async def set(self, *args, **kwargs):
        raise ConnectionError("redis down")


@pytest.mark.asyncio
async def test_region_survives_redis_outage(client, httpx_mock):
    httpx_mock.add_response(url=_KAKAO_URL, json=_DOCS)
    app.dependency_overrides[get_redis] = lambda: _BrokenRedis()
    try:
        resp = await client.get("/v1/map/region", params={"lat": 37.546, "lng": 127.071})
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert resp.json()["data"]["label"] == "광진구 화양동"


@pytest.mark.asyncio
async def test_region_treats_corrupt_cache_as_miss(client, httpx_mock):
    httpx_mock.add_response(url=_KAKAO_URL, json=_DOCS)
    redis = FakeRedis(decode_responses=False)
    await redis.set("region:37.546:127.071", b"{not-json", ex=60)
    app.dependency_overrides[get_redis] = lambda: redis
    try:
        resp = await client.get("/v1/map/region", params={"lat": 37.546, "lng": 127.071})
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert resp.json()["data"]["label"] == "광진구 화양동"
    # corrupt cache → miss → Kakao refetch + self-heal (overwrites with a valid value)
    assert len(httpx_mock.get_requests()) == 1
    healed = await redis.get("region:37.546:127.071")
    assert healed is not None and healed != b"{not-json"


@pytest.mark.asyncio
async def test_region_treats_non_utf8_cache_as_miss(client, httpx_mock):
    httpx_mock.add_response(url=_KAKAO_URL, json=_DOCS)
    redis = FakeRedis(decode_responses=False)
    await redis.set("region:37.546:127.071", b"\xff\xfe", ex=60)
    app.dependency_overrides[get_redis] = lambda: redis
    try:
        resp = await client.get("/v1/map/region", params={"lat": 37.546, "lng": 127.071})
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert resp.json()["data"]["label"] == "광진구 화양동"
