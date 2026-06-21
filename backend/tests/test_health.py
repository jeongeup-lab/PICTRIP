"""Smoke tests: app boots and responds with the standard envelope."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_returns_ok_envelope(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"] == {"status": "ok"}
    assert body["error"] is None
    assert "traceId" in body["meta"]


@pytest.mark.asyncio
async def test_meta_version(client: AsyncClient) -> None:
    resp = await client.get("/v1/meta/version")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["apiVersion"].startswith("1.0")


@pytest.mark.asyncio
async def test_openapi_schema_includes_all_6_domains(client: AsyncClient) -> None:
    resp = await client.get("/v1/openapi.json")
    assert resp.status_code == 200
    tags_in_schema = {
        tag
        for op in resp.json()["paths"].values()
        for method in op.values()
        for tag in method.get("tags", [])
    }
    expected = {
        "USR · user/auth",
        "TST · mood analysis",
        "SPT · spots",
        "IMG · image/matching (admin)",
        "MAP · map/crowd",
        "SYS · system/meta",
    }
    assert expected.issubset(tags_in_schema)
    # courses/recommendations removed in the refactor (6-module surface).
    assert "REC · recommendation" not in tags_in_schema
    assert "CRS · course" not in tags_in_schema


@pytest.mark.asyncio
async def test_trace_id_round_trips(client: AsyncClient) -> None:
    resp = await client.get("/health", headers={"X-Trace-Id": "abc1234567"})
    assert resp.headers["X-Trace-Id"] == "abc1234567"
    assert resp.json()["meta"]["traceId"] == "abc1234567"
