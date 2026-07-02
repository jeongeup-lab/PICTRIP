"""ApiV1CompatMiddleware: bare API paths get rewritten to /v1 (temp shim, 2026-07).

Guards the compat layer that keeps the mis-built v0.4.1 mobile release (which
baked an API base without the /v1 prefix) working until users update.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_bare_api_path_rewritten_to_v1(client: AsyncClient) -> None:
    # No /v1 prefix — as sent by the broken build. Must reach the v1 handler.
    bare = await client.get("/meta/version")
    assert bare.status_code == 200
    canonical = await client.get("/v1/meta/version")
    assert bare.json()["data"] == canonical.json()["data"]


@pytest.mark.asyncio
async def test_non_api_paths_pass_through_untouched(client: AsyncClient) -> None:
    # /health lives outside /v1 and its segment is not in the allowlist, so it
    # must NOT be rewritten to a non-existent /v1/health.
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["data"] == {"status": "ok"}


@pytest.mark.asyncio
async def test_already_prefixed_v1_not_double_prefixed(client: AsyncClient) -> None:
    # "v1" is not an allowlisted first-segment, so /v1/* is left alone.
    resp = await client.get("/v1/meta/version")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_unknown_bare_path_still_404(client: AsyncClient) -> None:
    # A segment we don't expose must not be rewritten into existence.
    resp = await client.get("/nope/whatever")
    assert resp.status_code == 404
