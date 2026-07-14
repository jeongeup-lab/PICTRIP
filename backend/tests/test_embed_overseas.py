from __future__ import annotations

import argparse

import pytest

from scripts import embed_overseas


def _args() -> argparse.Namespace:
    return argparse.Namespace(limit=None, concurrency=2, batch_size=50, pace=0.3)


@pytest.mark.asyncio
async def test_run_embed_invalidates_match_cache_before_and_after(
    redis_client_fake, monkeypatch: pytest.MonkeyPatch
) -> None:
    events: list[str] = []

    async def invalidate(redis: object) -> int:
        events.append("invalidate")
        return 0

    async def run_job(**kwargs: object) -> dict[str, int]:
        events.append("embed")
        return {"targets": 1, "embedded": 1, "failed": 0, "skipped": 0}

    monkeypatch.setattr(embed_overseas, "invalidate_all_match_cache", invalidate)
    monkeypatch.setattr(embed_overseas, "run_overseas_embedding_job", run_job)

    result = await embed_overseas._run_embed(redis_client_fake, _args())

    assert result["embedded"] == 1
    assert events == ["invalidate", "embed", "invalidate"]


@pytest.mark.asyncio
async def test_run_embed_invalidates_match_cache_when_job_fails(
    redis_client_fake, monkeypatch: pytest.MonkeyPatch
) -> None:
    events: list[str] = []

    async def invalidate(redis: object) -> int:
        events.append("invalidate")
        return 0

    async def run_job(**kwargs: object) -> dict[str, int]:
        events.append("embed")
        raise RuntimeError("embedding failed")

    monkeypatch.setattr(embed_overseas, "invalidate_all_match_cache", invalidate)
    monkeypatch.setattr(embed_overseas, "run_overseas_embedding_job", run_job)

    with pytest.raises(RuntimeError, match="embedding failed"):
        await embed_overseas._run_embed(redis_client_fake, _args())

    assert events == ["invalidate", "embed", "invalidate"]


@pytest.mark.asyncio
async def test_run_embed_continues_when_cache_invalidation_fails(
    redis_client_fake, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def broken_incr(*args: object, **kwargs: object) -> int:
        raise ConnectionError("redis unavailable")

    async def run_job(**kwargs: object) -> dict[str, int]:
        return {"targets": 1, "embedded": 1, "failed": 0, "skipped": 0}

    monkeypatch.setattr(redis_client_fake, "incr", broken_incr)
    monkeypatch.setattr(embed_overseas, "run_overseas_embedding_job", run_job)

    result = await embed_overseas._run_embed(redis_client_fake, _args())

    assert result["embedded"] == 1
