from __future__ import annotations

import asyncio
import math

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ml.embedding import ClipEmbedder
from app.modules.images.gallery_job import (
    centroid,
    collect_gallery_targets,
    embed_gallery_spots,
)
from app.web.errors import KtoApiUnavailable

_DIM = 512


def _one_hot(index: int) -> list[float]:
    return [1.0 if i == index else 0.0 for i in range(_DIM)]


@pytest.fixture
def fake_clip(monkeypatch: pytest.MonkeyPatch) -> None:
    def embed(_self: ClipEmbedder, image_bytes: bytes) -> list[float]:
        return _one_hot(image_bytes[-1] % _DIM)

    monkeypatch.setattr(ClipEmbedder, "embed_image", embed)


class _StubKto:
    def __init__(self, items_by_id: dict[str, list[dict]] | None = None, *, fail: bool = False):
        self._items = items_by_id or {}
        self._fail = fail

    async def call(self, _service, _operation, **params):
        if self._fail:
            raise KtoApiUnavailable()
        return self._items.get(params["contentId"], [])


async def _seed_spot(
    session: AsyncSession,
    cid: str,
    *,
    url: str | None = "https://img/first.jpg",
    lcls1: str | None = "NA",
) -> None:
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, first_image_url, "
            "show_flag, lcls_systm1) VALUES (:c, 12, :t, :u, 1, :l)"
        ),
        {"c": cid, "t": cid, "u": url, "l": lcls1},
    )


async def _seed_gallery_row(
    session: AsyncSession, cid: str, *, image_url: str = "https://img/first.jpg"
) -> None:
    await session.execute(
        text(
            "INSERT INTO spot_embeddings_gallery (content_id, embedding, image_url, image_count) "
            "VALUES (:c, CAST(:e AS halfvec(512)), :u, 1)"
        ),
        {"c": cid, "e": "[" + ",".join(["0.1"] * _DIM) + "]", "u": image_url},
    )


def test_centroid_is_normalised_mean() -> None:
    result = centroid([_one_hot(0), _one_hot(1)])
    expected = 1 / math.sqrt(2)
    assert result[0] == pytest.approx(expected)
    assert result[1] == pytest.approx(expected)
    assert all(v == 0.0 for v in result[2:])


@pytest.mark.asyncio
async def test_collect_targets_scopes_to_attraction_without_fresh_gallery(
    db_session: AsyncSession,
) -> None:
    await _seed_spot(db_session, "gt-attraction")
    await _seed_spot(db_session, "gt-shopping", lcls1="SH")
    await _seed_spot(db_session, "gt-fresh")
    await _seed_gallery_row(db_session, "gt-fresh")
    await _seed_spot(db_session, "gt-stale")
    await _seed_gallery_row(db_session, "gt-stale", image_url="https://img/old.jpg")
    await db_session.flush()

    targets = await collect_gallery_targets(db_session)
    ids = {cid for cid, _url in targets if cid.startswith("gt-")}

    assert ids == {"gt-attraction", "gt-stale"}


@pytest.mark.asyncio
async def test_embed_writes_centroid_of_first_and_detail_images(
    db_session: AsyncSession, httpx_mock, fake_clip: None
) -> None:
    await _seed_spot(db_session, "gj-1")
    await db_session.flush()
    kto = _StubKto(
        {
            "gj-1": [
                {"originimgurl": "https://img/extra-a.jpg"},
                {"originimgurl": "https://img/extra-b.jpg"},
            ]
        }
    )
    httpx_mock.add_response(url="https://img/first.jpg", content=b"\x00")
    httpx_mock.add_response(url="https://img/extra-a.jpg", content=b"\x01")
    httpx_mock.add_response(url="https://img/extra-b.jpg", content=b"\x02")

    async with AsyncClient() as client:
        result = await embed_gallery_spots(
            db_session,
            [("gj-1", "https://img/first.jpg")],
            kto=kto,
            client=client,
            dl_sem=asyncio.Semaphore(4),
        )

    assert result.written == 1 and result.failed == 0
    row = (
        await db_session.execute(
            text(
                "SELECT image_url, image_count, embedding::text FROM spot_embeddings_gallery "
                "WHERE content_id = 'gj-1'"
            )
        )
    ).one()
    assert row.image_url == "https://img/first.jpg"
    assert row.image_count == 3
    first_dim = float(row[2].strip("[]").split(",")[0])
    assert first_dim == pytest.approx(1 / math.sqrt(3), rel=1e-2)


@pytest.mark.asyncio
async def test_kto_failure_writes_no_row(
    db_session: AsyncSession, httpx_mock, fake_clip: None
) -> None:
    await _seed_spot(db_session, "gj-kto")
    await db_session.flush()

    async with AsyncClient() as client:
        result = await embed_gallery_spots(
            db_session,
            [("gj-kto", "https://img/first.jpg")],
            kto=_StubKto(fail=True),
            client=client,
            dl_sem=asyncio.Semaphore(4),
        )

    assert result.failed == 1 and result.by_status == {"kto_failed": 1}
    count = await db_session.scalar(
        text("SELECT count(*) FROM spot_embeddings_gallery WHERE content_id = 'gj-kto'")
    )
    assert count == 0


@pytest.mark.asyncio
async def test_all_downloads_failed_writes_no_row(
    db_session: AsyncSession, httpx_mock, fake_clip: None
) -> None:
    await _seed_spot(db_session, "gj-dl")
    await db_session.flush()
    httpx_mock.add_response(url="https://img/first.jpg", status_code=404)

    async with AsyncClient() as client:
        result = await embed_gallery_spots(
            db_session,
            [("gj-dl", "https://img/first.jpg")],
            kto=_StubKto(),
            client=client,
            dl_sem=asyncio.Semaphore(4),
        )

    assert result.failed == 1 and result.by_status == {"no_images": 1}
    count = await db_session.scalar(
        text("SELECT count(*) FROM spot_embeddings_gallery WHERE content_id = 'gj-dl'")
    )
    assert count == 0


@pytest.mark.asyncio
async def test_empty_detail_gallery_falls_back_to_first_image_only(
    db_session: AsyncSession, httpx_mock, fake_clip: None
) -> None:
    await _seed_spot(db_session, "gj-solo")
    await db_session.flush()
    httpx_mock.add_response(url="https://img/first.jpg", content=b"\x07")

    async with AsyncClient() as client:
        result = await embed_gallery_spots(
            db_session,
            [("gj-solo", "https://img/first.jpg")],
            kto=_StubKto(),
            client=client,
            dl_sem=asyncio.Semaphore(4),
        )

    assert result.written == 1
    row = (
        await db_session.execute(
            text("SELECT image_count FROM spot_embeddings_gallery WHERE content_id = 'gj-solo'")
        )
    ).one()
    assert row.image_count == 1


@pytest.mark.asyncio
async def test_embed_persists_detail_images_with_copyright(
    db_session: AsyncSession, httpx_mock, fake_clip: None
) -> None:
    await _seed_spot(db_session, "gj-img")
    await db_session.flush()
    kto = _StubKto(
        {
            "gj-img": [
                {
                    "originimgurl": "https://img/a.jpg",
                    "smallimageurl": "https://img/a-s.jpg",
                    "cpyrhtDivCd": "Type1",
                },
                {"originimgurl": "https://img/b.jpg", "cpyrhtDivCd": "Type3"},
            ]
        }
    )
    httpx_mock.add_response(url="https://img/first.jpg", content=b"\x00")
    httpx_mock.add_response(url="https://img/a.jpg", content=b"\x01")
    httpx_mock.add_response(url="https://img/b.jpg", content=b"\x02")

    async with AsyncClient() as client:
        await embed_gallery_spots(
            db_session,
            [("gj-img", "https://img/first.jpg")],
            kto=kto,
            client=client,
            dl_sem=asyncio.Semaphore(4),
        )

    rows = (
        await db_session.execute(
            text(
                "SELECT origin_image_url, small_image_url, cpyrht_div_cd FROM spot_images "
                "WHERE content_id = 'gj-img' ORDER BY sort_order"
            )
        )
    ).all()
    assert [r.origin_image_url for r in rows] == ["https://img/a.jpg", "https://img/b.jpg"]
    assert [r.small_image_url for r in rows] == ["https://img/a-s.jpg", None]
    assert [r.cpyrht_div_cd for r in rows] == ["Type1", "Type3"]


@pytest.mark.asyncio
async def test_kto_failure_leaves_detail_images_untouched(
    db_session: AsyncSession, httpx_mock, fake_clip: None
) -> None:
    await _seed_spot(db_session, "gj-keep")
    await db_session.execute(
        text(
            "INSERT INTO spot_images (content_id, origin_image_url, sort_order) "
            "VALUES ('gj-keep', 'https://img/kept.jpg', 0)"
        )
    )
    await db_session.flush()

    async with AsyncClient() as client:
        await embed_gallery_spots(
            db_session,
            [("gj-keep", "https://img/first.jpg")],
            kto=_StubKto(fail=True),
            client=client,
            dl_sem=asyncio.Semaphore(4),
        )

    kept = await db_session.scalar(
        text("SELECT origin_image_url FROM spot_images WHERE content_id = 'gj-keep'")
    )
    assert kept == "https://img/kept.jpg"
