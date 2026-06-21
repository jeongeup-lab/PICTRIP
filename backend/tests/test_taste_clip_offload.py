"""PR-A: the blocking CLIP embed must run off the event loop (asyncio.to_thread).

The CPU-bound torch inference in `embed_image` would otherwise stall the whole
async worker. We assert the embed runs on a *worker* thread, not the event-loop
thread. `find_neighbors_by_vector` is stubbed so no DB session is required.
"""

from __future__ import annotations

import threading

import pytest

from app.modules.taste import services as taste_services


@pytest.mark.asyncio
async def test_photo_search_offloads_clip_to_a_worker_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    main_thread = threading.current_thread()
    captured: dict[str, threading.Thread] = {}

    def _fake_embed(_self: object, image_bytes: bytes) -> list[float]:
        captured["thread"] = threading.current_thread()
        return [0.0] * 512

    from app.core.embedding import ClipEmbedder

    monkeypatch.setattr(ClipEmbedder, "embed_image", _fake_embed)

    async def _fake_neighbors(_session: object, _embedding: list[float], *, limit: int) -> list:
        return []

    monkeypatch.setattr(taste_services, "find_neighbors_by_vector", _fake_neighbors)

    result = await taste_services.photo_search(None, b"fake-bytes", limit=5)  # type: ignore[arg-type]

    assert result == []
    assert "thread" in captured, "embed_image was never called"
    assert captured["thread"] is not main_thread, (
        "CLIP embed ran on the event-loop thread — it must be offloaded via asyncio.to_thread"
    )
