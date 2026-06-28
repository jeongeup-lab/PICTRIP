"""IMG embedding job — embed_spots records successes/failures, collect_targets scopes.

Exercises the shared embed path (CLI backfill + admin re-embed button) against the
per-test rolled-back session: CLIP is faked (no model load) and image downloads
are mocked (no network), so we assert the DB side-effects — ``spot_embeddings``
upsert + ``embedding_failures`` upsert/clear — and the target-selection filters.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.embedding import ClipEmbedder
from app.modules.images.embedding_job import collect_targets, embed_spots


@pytest.fixture
def fake_clip(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch CLIP at the class boundary (no model load).

    Must patch the CLASS, not the singleton instance — an instance-attribute
    monkeypatch leaks onto the shared ``embedder`` and shadows the class-level
    patching other suites (taste/photo-search) rely on.
    """
    monkeypatch.setattr(ClipEmbedder, "embed_image", lambda _self, _b: [0.1] * 512)


async def _seed_spot(
    session: AsyncSession, cid: str, url: str | None = "https://img/x.jpg", *, days_ago: int = 1
) -> None:
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, first_image_url, "
            "show_flag, synced_at) VALUES "
            "(:c, 12, :t, :u, 1, now() - make_interval(days => :d))"
        ),
        {"c": cid, "t": cid, "u": url, "d": days_ago},
    )


@pytest.mark.asyncio
async def test_embed_spots_records_success_and_failure(
    db_session: AsyncSession, httpx_mock, fake_clip: None
) -> None:
    await _seed_spot(db_session, "ok-1", "https://img/ok-1.jpg")
    await _seed_spot(db_session, "dl-1", "https://img/dl-1.jpg")
    await db_session.flush()

    httpx_mock.add_response(url="https://img/ok-1.jpg", content=b"\xff\xd8fakejpeg")
    httpx_mock.add_response(url="https://img/dl-1.jpg", status_code=404)

    targets = [("ok-1", "https://img/ok-1.jpg"), ("dl-1", "https://img/dl-1.jpg")]
    async with AsyncClient() as client:
        result = await embed_spots(db_session, targets, client=client, dl_sem=asyncio.Semaphore(4))

    assert result.written == 1
    assert result.failed == 1
    assert result.by_status == {"ok": 1, "download_failed": 1}

    emb = (await db_session.execute(text("SELECT content_id FROM spot_embeddings"))).scalars().all()
    assert emb == ["ok-1"]
    fails = (
        await db_session.execute(
            text("SELECT content_id, reason, attempts FROM embedding_failures")
        )
    ).all()
    assert fails == [("dl-1", "download_failed", 1)]


@pytest.mark.asyncio
async def test_embed_spots_clears_failure_on_later_success(
    db_session: AsyncSession, httpx_mock, fake_clip: None
) -> None:
    await _seed_spot(db_session, "sp-1", "https://img/sp-1.jpg")
    # Pre-existing failure row for the same spot.
    await db_session.execute(
        text(
            "INSERT INTO embedding_failures (content_id, reason, attempts) "
            "VALUES ('sp-1', 'download_failed', 2)"
        )
    )
    await db_session.flush()

    httpx_mock.add_response(url="https://img/sp-1.jpg", content=b"\xff\xd8ok")
    async with AsyncClient() as client:
        await embed_spots(
            db_session,
            [("sp-1", "https://img/sp-1.jpg")],
            client=client,
            dl_sem=asyncio.Semaphore(2),
        )

    # success → embedding written AND failure row removed.
    assert (
        await db_session.execute(
            text("SELECT count(*) FROM spot_embeddings WHERE content_id='sp-1'")
        )
    ).scalar_one() == 1
    assert (
        await db_session.execute(text("SELECT count(*) FROM embedding_failures"))
    ).scalar_one() == 0


@pytest.mark.asyncio
async def test_embed_spots_increments_attempts_on_repeat_failure(
    db_session: AsyncSession, httpx_mock, fake_clip: None
) -> None:
    await _seed_spot(db_session, "bad-1", "https://img/bad-1.jpg")
    await db_session.execute(
        text(
            "INSERT INTO embedding_failures (content_id, reason, attempts) "
            "VALUES ('bad-1', 'download_failed', 1)"
        )
    )
    await db_session.flush()

    httpx_mock.add_response(url="https://img/bad-1.jpg", status_code=500)
    async with AsyncClient() as client:
        await embed_spots(
            db_session,
            [("bad-1", "https://img/bad-1.jpg")],
            client=client,
            dl_sem=asyncio.Semaphore(2),
        )

    attempts = (
        await db_session.execute(
            text("SELECT attempts FROM embedding_failures WHERE content_id='bad-1'")
        )
    ).scalar_one()
    assert attempts == 2


@pytest.mark.asyncio
async def test_collect_targets_scopes(db_session: AsyncSession) -> None:
    # image-bearing, no embedding → target
    await _seed_spot(db_session, "miss-old", "https://img/a.jpg", days_ago=10)
    await _seed_spot(db_session, "miss-new", "https://img/b.jpg", days_ago=0)
    # no image → never a target
    await _seed_spot(db_session, "no-img", None)
    # already embedded → excluded
    await _seed_spot(db_session, "done", "https://img/c.jpg")
    await db_session.execute(
        text("INSERT INTO spot_embeddings (content_id, embedding) VALUES ('done', :v)"),
        {"v": "[" + ",".join(["0.0"] * 512) + "]"},
    )
    # a failure record on miss-old
    await db_session.execute(
        text(
            "INSERT INTO embedding_failures (content_id, reason) VALUES ('miss-old', 'clip_error')"
        )
    )
    await db_session.flush()

    all_targets = {c for c, _ in await collect_targets(db_session)}
    assert all_targets == {"miss-old", "miss-new"}

    failed_only = {c for c, _ in await collect_targets(db_session, only_failed=True)}
    assert failed_only == {"miss-old"}

    since = datetime.now(tz=UTC) - timedelta(days=1)
    recent = {c for c, _ in await collect_targets(db_session, since=since)}
    assert recent == {"miss-new"}
