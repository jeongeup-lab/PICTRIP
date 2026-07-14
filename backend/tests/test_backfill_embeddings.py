from __future__ import annotations

import argparse

import pytest

from app.modules.images.embedding_job import EmbedResult
from scripts import backfill_embeddings


@pytest.mark.asyncio
async def test_run_backfill_invalidates_match_cache_before_and_after(
    redis_client_fake, monkeypatch: pytest.MonkeyPatch
) -> None:
    events: list[str] = []

    async def invalidate(redis: object) -> int:
        events.append("invalidate")
        return 0

    async def run_job(**kwargs: object) -> EmbedResult:
        events.append("embed")
        assert kwargs["failure_reason"] == "source_changed"
        return EmbedResult(written=1)

    monkeypatch.setattr(backfill_embeddings, "invalidate_all_match_cache", invalidate)
    monkeypatch.setattr(backfill_embeddings, "run_embedding_job", run_job)
    args = argparse.Namespace(
        only_failed=True,
        failure_reason="source_changed",
        limit=None,
        batch_size=100,
        concurrency=8,
    )

    result = await backfill_embeddings._run_backfill(redis_client_fake, args)

    assert result.written == 1
    assert events == ["invalidate", "embed", "invalidate"]


@pytest.mark.asyncio
async def test_run_backfill_invalidates_match_cache_when_job_fails(
    redis_client_fake, monkeypatch: pytest.MonkeyPatch
) -> None:
    events: list[str] = []

    async def invalidate(redis: object) -> int:
        events.append("invalidate")
        return 0

    async def run_job(**kwargs: object) -> EmbedResult:
        events.append("embed")
        raise RuntimeError("embedding failed")

    monkeypatch.setattr(backfill_embeddings, "invalidate_all_match_cache", invalidate)
    monkeypatch.setattr(backfill_embeddings, "run_embedding_job", run_job)
    args = argparse.Namespace(
        only_failed=False,
        failure_reason=None,
        limit=None,
        batch_size=100,
        concurrency=8,
    )

    with pytest.raises(RuntimeError, match="embedding failed"):
        await backfill_embeddings._run_backfill(redis_client_fake, args)

    assert events == ["invalidate", "embed", "invalidate"]
