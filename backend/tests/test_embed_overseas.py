from __future__ import annotations

import argparse

import pytest

from scripts import embed_overseas


def _args() -> argparse.Namespace:
    return argparse.Namespace(limit=None, concurrency=2, batch_size=50, pace=0.3)


@pytest.mark.asyncio
async def test_run_embed_recomputes_matches_after_job(
    redis_client_fake, monkeypatch: pytest.MonkeyPatch
) -> None:
    events: list[str] = []

    async def recompute() -> dict[str, int]:
        events.append("recompute")
        return {"targets": 0, "matched": 0, "empty": 0}

    async def run_job(**kwargs: object) -> dict[str, int]:
        events.append("embed")
        return {"targets": 1, "embedded": 1, "failed": 0, "skipped": 0}

    monkeypatch.setattr(embed_overseas, "recompute_all_matches", recompute)
    monkeypatch.setattr(embed_overseas, "run_overseas_embedding_job", run_job)

    result = await embed_overseas._run_embed(redis_client_fake, _args())

    assert result["embedded"] == 1
    assert events == ["embed", "recompute"]


@pytest.mark.asyncio
async def test_run_embed_recomputes_matches_when_job_fails(
    redis_client_fake, monkeypatch: pytest.MonkeyPatch
) -> None:
    events: list[str] = []

    async def recompute() -> dict[str, int]:
        events.append("recompute")
        return {"targets": 0, "matched": 0, "empty": 0}

    async def run_job(**kwargs: object) -> dict[str, int]:
        events.append("embed")
        raise RuntimeError("embedding failed")

    monkeypatch.setattr(embed_overseas, "recompute_all_matches", recompute)
    monkeypatch.setattr(embed_overseas, "run_overseas_embedding_job", run_job)

    with pytest.raises(RuntimeError, match="embedding failed"):
        await embed_overseas._run_embed(redis_client_fake, _args())

    assert events == ["embed", "recompute"]
