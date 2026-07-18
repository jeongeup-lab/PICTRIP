from __future__ import annotations

from collections.abc import Callable

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.embedding import ClipEmbedder
from app.modules.feed import embedding_job
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
    assert counters["skipped"] == 0

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


@pytest.mark.asyncio
async def test_job_skips_embedding_when_source_image_changes(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    old_url = "https://commons/source-old.jpg"
    new_url = "https://commons/source-new.jpg"
    await _seed(db_session, "QS1", old_url, embedded=False)
    await db_session.flush()

    async def change_source(
        oid: int, image_url: str, *args: object
    ) -> tuple[int, str, list[float]]:
        await db_session.execute(
            text("UPDATE overseas_spots SET image_url = :url WHERE id = :oid"),
            {"url": new_url, "oid": oid},
        )
        await db_session.commit()
        return oid, image_url, [0.1] * 512

    monkeypatch.setattr(embedding_job, "_embed_one", change_source)

    counters = await run_overseas_embedding_job(session_factory=make_factory(db_session))

    row = (
        await db_session.execute(
            text(
                "SELECT image_url, embedding IS NULL AS embedding_is_null "
                "FROM overseas_spots WHERE wikidata_id = 'QS1'"
            )
        )
    ).one()
    assert counters == {"targets": 1, "embedded": 0, "failed": 0, "skipped": 1}
    assert row.image_url == new_url
    assert row.embedding_is_null is True
