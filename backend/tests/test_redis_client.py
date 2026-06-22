"""Tests for async Redis client + fakeredis fixture."""

import pytest


@pytest.mark.asyncio
async def test_fake_redis_fixture_yields_working_client(redis_client_fake):
    await redis_client_fake.set("foo", "bar")
    val = await redis_client_fake.get("foo")
    assert val == b"bar" or val == "bar"
