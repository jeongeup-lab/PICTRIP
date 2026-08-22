from __future__ import annotations

import argparse

import pytest

from app.modules.images.embedding_job import EmbedResult
from scripts import backfill_embeddings


@pytest.mark.asyncio
async def test_run_backfill_recomputes_matches_after_job(
    redis_client_fake, monkeypatch: pytest.MonkeyPatch
) -> None:
    events: list[str] = []

    async def recompute() -> dict[str, int]:
        events.append("recompute")
        return {"targets": 0, "matched": 0, "empty": 0}

    async def run_job(**kwargs: object) -> EmbedResult:
        events.append("embed")
        assert kwargs["failure_reason"] == "source_changed"
        return EmbedResult(written=1)

    monkeypatch.setattr(backfill_embeddings, "recompute_all_matches", recompute)
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
    assert events == ["embed", "recompute"]


@pytest.mark.asyncio
async def test_run_backfill_recomputes_matches_when_job_fails(
    redis_client_fake, monkeypatch: pytest.MonkeyPatch
) -> None:
    events: list[str] = []

    async def recompute() -> dict[str, int]:
        events.append("recompute")
        return {"targets": 0, "matched": 0, "empty": 0}

    async def run_job(**kwargs: object) -> EmbedResult:
        events.append("embed")
        raise RuntimeError("embedding failed")

    monkeypatch.setattr(backfill_embeddings, "recompute_all_matches", recompute)
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

    assert events == ["embed", "recompute"]
