"""FEED overseas embedding job — run_overseas_embedding_job fills embedding NULL rows.

Mirrors the KTO embedding-job suite: CLIP is faked (no model load), image
downloads are mocked (no network). The job owns its own sessions, so tests inject
a factory bound to the per-test rolled-back connection and assert both the
returned counters and the DB side-effect on ``overseas_spots.embedding``.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.embedding import ClipEmbedder
from app.modules.feed.embedding_job import run_overseas_embedding_job

_UA = "PicTrip/1.0 (https://pictrip.org)"


@pytest.fixture
def fake_clip(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ClipEmbedder, "embed_image", lambda _self, _b: [0.1] * 512)


def make_factory(session: AsyncSession) -> Callable[[], AsyncSession]:
    conn = session.bind

    def factory() -> AsyncSession:
        return AsyncSession(
            bind=conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
        )

    return factory


async def _seed(
    session: AsyncSession, wikidata_id: str, image_url: str, *, embedded: bool = False
) -> None:
    await session.execute(
        text(
            "INSERT INTO overseas_spots (wikidata_id, name_ko, country_code, "
            "country_name_ko, image_url, image_source_url, embedding) VALUES "
            "(:w, :w, 'FR', '프랑스', :u, :u, :emb)"
        ),
        {
            "w": wikidata_id,
            "u": image_url,
            "emb": ("[" + ",".join(["0.0"] * 512) + "]") if embedded else None,
        },
    )


@pytest.mark.asyncio
async def test_job_embeds_missing_rows(
    db_session: AsyncSession, httpx_mock, fake_clip: None
) -> None:
    await _seed(db_session, "QE1", "https://commons/qe1.jpg", embedded=False)
    await _seed(db_session, "QE2", "https://commons/qe2.jpg", embedded=True)
    await db_session.flush()

    httpx_mock.add_response(
        url="https://commons/qe1.jpg",
        content=b"\xff\xd8fakejpeg",
        match_headers={"User-Agent": _UA},
    )

    counters = await run_overseas_embedding_job(session_factory=make_factory(db_session))

    assert counters["targets"] == 1
    assert counters["embedded"] == 1
    assert counters["failed"] == 0

    row = (
        await db_session.execute(
            text("SELECT embedding IS NOT NULL FROM overseas_spots WHERE wikidata_id='QE1'")
        )
    ).scalar()
    assert row is True


@pytest.mark.asyncio
async def test_job_retries_rate_limited_download(
    db_session: AsyncSession, httpx_mock, fake_clip: None
) -> None:
    await _seed(db_session, "QR1", "https://commons/qr1.jpg", embedded=False)
    await db_session.flush()

    httpx_mock.add_response(
        url="https://commons/qr1.jpg", status_code=429, headers={"Retry-After": "0"}
    )
    httpx_mock.add_response(url="https://commons/qr1.jpg", status_code=429)
    httpx_mock.add_response(
        url="https://commons/qr1.jpg",
        content=b"\xff\xd8fakejpeg",
        match_headers={"User-Agent": _UA},
    )

    counters = await run_overseas_embedding_job(
        session_factory=make_factory(db_session), download_pace=0.0, backoff_base=0.0
    )

    assert counters["embedded"] == 1
    assert counters["failed"] == 0


@pytest.mark.asyncio
async def test_job_fails_after_exhausting_rate_limit_retries(
    db_session: AsyncSession, httpx_mock, fake_clip: None
) -> None:
    await _seed(db_session, "QR2", "https://commons/qr2.jpg", embedded=False)
    await db_session.flush()

    for _ in range(6):
        httpx_mock.add_response(url="https://commons/qr2.jpg", status_code=429)

    counters = await run_overseas_embedding_job(
        session_factory=make_factory(db_session), download_pace=0.0, backoff_base=0.0
    )

    assert counters["embedded"] == 0
    assert counters["failed"] == 1


@pytest.mark.asyncio
async def test_job_counts_download_failure(
    db_session: AsyncSession, httpx_mock, fake_clip: None
) -> None:
    await _seed(db_session, "QF1", "https://commons/qf1.jpg", embedded=False)
    await db_session.flush()

    httpx_mock.add_response(url="https://commons/qf1.jpg", status_code=404)

    counters = await run_overseas_embedding_job(session_factory=make_factory(db_session))

    assert counters["targets"] == 1
    assert counters["embedded"] == 0
    assert counters["failed"] == 1

    still_null = (
        await db_session.execute(
            text("SELECT embedding IS NULL FROM overseas_spots WHERE wikidata_id='QF1'")
        )
    ).scalar()
    assert still_null is True
