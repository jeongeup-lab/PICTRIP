from __future__ import annotations

from dataclasses import dataclass

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.db import get_db
from app.core.redis import get_redis
from app.main import app
from app.modules.feed import repositories
from app.modules.feed.services import matching

_DIM = 512


def _literal(vec: list[float]) -> str:
    return "[" + ",".join(f"{v:.6f}" for v in vec) + "]"


_CLOSE = [0.1] * _DIM
_NEAR = [0.09, *([0.1] * (_DIM - 1))]
_FAR = [0.1 if i % 2 == 0 else -0.1 for i in range(_DIM)]


@pytest.fixture(autouse=True)
def _wire(db_session, redis_client_fake):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_redis] = lambda: redis_client_fake
    yield
    app.dependency_overrides.clear()


async def _insert_overseas(session: AsyncSession, *, embedding: list[float] | None) -> int:
    row = (
        await session.execute(
            text(
                "INSERT INTO overseas_spots (wikidata_id, name_ko, country_code, "
                "country_name_ko, image_url, image_source_url, embedding) "
                "VALUES (:qid, :name, 'FR', '프랑스', 'https://img/x', 'https://src/x', "
                "CAST(:emb AS halfvec(512))) RETURNING id"
            ),
            {
                "qid": f"Q{id(session) % 100000}{'e' if embedding else 'n'}",
                "name": "해외명소",
                "emb": _literal(embedding) if embedding is not None else None,
            },
        )
    ).scalar_one()
    await session.commit()
    return int(row)


async def _insert_spot(
    session: AsyncSession,
    content_id: str,
    vec: list[float],
    *,
    overview: str | None,
    show_flag: int = 1,
    lcls1: str | None = "NA",
    lcls2: str | None = None,
) -> None:
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, first_image_url, "
            "addr1, mapx, mapy, show_flag, lcls_systm1, lcls_systm2) "
            "VALUES (:cid, 12, :t, 'http://kto/p.jpg', 'addr1', 127.0, 37.0, :show, "
            ":lcls1, :lcls2) "
            "ON CONFLICT (content_id) DO NOTHING"
        ),
        {
            "cid": content_id,
            "t": f"title-{content_id}",
            "show": show_flag,
            "lcls1": lcls1,
            "lcls2": lcls2,
        },
    )
    await session.execute(
        text(
            "INSERT INTO spot_embeddings (content_id, embedding, image_url) "
            "VALUES (:cid, CAST(:emb AS halfvec(512)), 'http://kto/p.jpg') "
            "ON CONFLICT (content_id) DO NOTHING"
        ),
        {"cid": content_id, "emb": _literal(vec)},
    )
    if overview is not None:
        await session.execute(
            text(
                "INSERT INTO spot_details (content_id, content_type_id, overview) "
                "VALUES (:cid, 12, :ov) ON CONFLICT (content_id) DO NOTHING"
            ),
            {"cid": content_id, "ov": overview},
        )
    await session.commit()


async def _insert_gallery(
    session: AsyncSession,
    content_id: str,
    vec: list[float],
    *,
    image_url: str = "http://kto/p.jpg",
    image_count: int = 3,
) -> None:
    await session.execute(
        text(
            "INSERT INTO spot_embeddings_gallery (content_id, embedding, image_url, image_count) "
            "VALUES (:cid, CAST(:emb AS halfvec(512)), :url, :cnt) "
            "ON CONFLICT (content_id) DO NOTHING"
        ),
        {"cid": content_id, "emb": _literal(vec), "url": image_url, "cnt": image_count},
    )
    await session.commit()


@dataclass
class Seeded:
    overseas_id: int


@pytest.fixture
async def seeded_matching(db_session) -> Seeded:
    oid = await _insert_overseas(db_session, embedding=_CLOSE)
    await _insert_spot(db_session, "mt_a", _CLOSE, overview="첫 문장이다. 둘째 문장.")
    await _insert_spot(db_session, "mt_b", _CLOSE, overview="다른 소개문이다.")
    await _insert_spot(db_session, "mt_c", _NEAR, overview=None)
    await matching.precompute_matches(db_session)
    return Seeded(overseas_id=oid)


@pytest.fixture
async def seeded_matching_far(db_session) -> Seeded:
    oid = await _insert_overseas(db_session, embedding=_CLOSE)
    await _insert_spot(db_session, "mt_far_a", _FAR, overview="멀리 있다.")
    await _insert_spot(db_session, "mt_far_b", _FAR, overview="멀리 있다 둘.")
    await matching.precompute_matches(db_session)
    return Seeded(overseas_id=oid)


@pytest.fixture
async def seeded_overseas_no_embedding(db_session) -> int:
    return await _insert_overseas(db_session, embedding=None)


async def test_matches_returns_similar_domestic(client, seeded_matching):
    res = await client.get(f"/v1/overseas/{seeded_matching.overseas_id}/matches")
    body = res.json()
    assert res.status_code == 200 and body["error"] is None
    matches = body["data"]["matches"]
    assert len(matches) == 3
    assert {"contentId", "title", "regionLabel", "imageUrl", "overviewFirst"} <= set(matches[0])


async def test_matches_threshold_filters_far_spots(client, seeded_matching_far):
    res = await client.get(f"/v1/overseas/{seeded_matching_far.overseas_id}/matches")
    content_ids = {row["contentId"] for row in res.json()["data"]["matches"]}
    assert content_ids.isdisjoint({"mt_far_a", "mt_far_b"})


async def test_precompute_writes_contiguous_ranks(db_session, seeded_matching):
    rows = (
        await db_session.execute(
            text(
                "SELECT rank, content_id, distance FROM overseas_spot_matches "
                "WHERE overseas_id = :oid ORDER BY rank"
            ),
            {"oid": seeded_matching.overseas_id},
        )
    ).all()
    assert [row.rank for row in rows] == [1, 2, 3]
    assert [row.distance for row in rows] == sorted(row.distance for row in rows)


async def test_precompute_replaces_previous_result(db_session, seeded_matching):
    await db_session.execute(
        text("UPDATE spots SET show_flag = 0 WHERE content_id IN ('mt_b', 'mt_c')")
    )
    await db_session.commit()

    await matching.precompute_matches(db_session)

    remaining = (
        await db_session.execute(
            text("SELECT content_id FROM overseas_spot_matches WHERE overseas_id = :oid"),
            {"oid": seeded_matching.overseas_id},
        )
    ).scalars()
    assert set(remaining) == {"mt_a"}


async def test_precompute_counts_empty_results(db_session, seeded_matching_far):
    counters = await matching.precompute_matches(db_session)
    assert counters["targets"] >= 1
    assert counters["empty"] >= 1


async def test_match_drops_when_source_image_moves(client, db_session, seeded_matching):
    """이미지가 바뀌면 그 사진으로 맺은 유사도는 더 이상 근거가 아니다."""
    await db_session.execute(
        text("UPDATE spots SET first_image_url = 'http://kto/moved.jpg' WHERE content_id = 'mt_a'")
    )
    await db_session.commit()

    res = await client.get(f"/v1/overseas/{seeded_matching.overseas_id}/matches")

    content_ids = {row["contentId"] for row in res.json()["data"]["matches"]}
    assert "mt_a" not in content_ids


async def test_match_drops_when_spot_is_deactivated(client, db_session, seeded_matching):
    await db_session.execute(text("UPDATE spots SET show_flag = 0 WHERE content_id = 'mt_a'"))
    await db_session.commit()

    res = await client.get(f"/v1/overseas/{seeded_matching.overseas_id}/matches")

    content_ids = {row["contentId"] for row in res.json()["data"]["matches"]}
    assert "mt_a" not in content_ids


async def test_neighbor_search_excludes_inactive_spots(db_session):
    oid = await _insert_overseas(db_session, embedding=_CLOSE)
    await _insert_spot(
        db_session,
        "mt_hidden_neighbor",
        _CLOSE,
        overview=None,
        show_flag=0,
    )
    await _insert_spot(db_session, "mt_active_neighbor", _NEAR, overview=None)

    neighbors = await repositories.find_domestic_neighbors(db_session, oid, limit=10_000)
    content_ids = {content_id for content_id, _image_url, _distance in neighbors}

    assert "mt_active_neighbor" in content_ids
    assert "mt_hidden_neighbor" not in content_ids


async def test_neighbor_search_excludes_uncategorized_spots(db_session):
    oid = await _insert_overseas(db_session, embedding=_CLOSE)
    await _insert_spot(db_session, "mt_categorized", _CLOSE, overview=None, lcls1="NA")
    await _insert_spot(db_session, "mt_uncategorized", _CLOSE, overview=None, lcls1=None)

    neighbors = await repositories.find_domestic_neighbors(db_session, oid, limit=10_000)
    content_ids = {content_id for content_id, _image_url, _distance in neighbors}

    assert "mt_categorized" in content_ids
    assert "mt_uncategorized" not in content_ids


async def test_neighbor_search_excludes_non_attraction_categories(db_session):
    oid = await _insert_overseas(db_session, embedding=_CLOSE)
    await _insert_spot(db_session, "mt_attraction", _CLOSE, overview=None, lcls1="NA")
    await _insert_spot(db_session, "mt_shopping", _CLOSE, overview=None, lcls1="SH")
    await _insert_spot(db_session, "mt_food", _CLOSE, overview=None, lcls1="FD", lcls2="FD01")
    await _insert_spot(db_session, "mt_cafe", _CLOSE, overview=None, lcls1="FD", lcls2="FD05")
    await _insert_spot(db_session, "mt_leisure", _CLOSE, overview=None, lcls1="LS")

    neighbors = await repositories.find_domestic_neighbors(db_session, oid, limit=10_000)
    content_ids = {content_id for content_id, _image_url, _distance in neighbors}

    assert "mt_attraction" in content_ids
    assert content_ids.isdisjoint({"mt_shopping", "mt_food", "mt_cafe", "mt_leisure"})


async def test_neighbor_search_uses_gallery_distance_when_closer(db_session):
    oid = await _insert_overseas(db_session, embedding=_CLOSE)
    await _insert_spot(db_session, "mt_gal_far_single", _FAR, overview=None)
    await _insert_gallery(db_session, "mt_gal_far_single", _NEAR)

    neighbors = await repositories.find_domestic_neighbors(db_session, oid, limit=10_000)
    rows = {content_id: distance for content_id, _image_url, distance in neighbors}

    assert "mt_gal_far_single" in rows
    assert [cid for cid, _url, _d in neighbors].count("mt_gal_far_single") == 1
    assert rows["mt_gal_far_single"] < 0.1


async def test_neighbor_search_gallery_respects_attraction_gate(db_session):
    oid = await _insert_overseas(db_session, embedding=_CLOSE)
    await _insert_spot(db_session, "mt_gal_shop", _FAR, overview=None, lcls1="SH")
    await _insert_gallery(db_session, "mt_gal_shop", _CLOSE)

    neighbors = await repositories.find_domestic_neighbors(db_session, oid, limit=10_000)
    content_ids = {content_id for content_id, _image_url, _distance in neighbors}

    assert "mt_gal_shop" not in content_ids


async def test_neighbor_search_ignores_stale_gallery_row(db_session):
    oid = await _insert_overseas(db_session, embedding=_CLOSE)
    await _insert_spot(db_session, "mt_gal_stale", _FAR, overview=None)
    await _insert_gallery(db_session, "mt_gal_stale", _CLOSE, image_url="http://kto/old.jpg")

    neighbors = await repositories.find_domestic_neighbors(db_session, oid, limit=10_000)
    rows = {content_id: distance for content_id, _image_url, distance in neighbors}

    assert rows["mt_gal_stale"] > 0.1


async def test_neighbor_search_returns_empty_without_overseas_embedding(db_session):
    oid = await _insert_overseas(db_session, embedding=None)
    await _insert_spot(db_session, "mt_no_target_embedding", _CLOSE, overview=None)

    neighbors = await repositories.find_domestic_neighbors(db_session, oid, limit=10_000)

    assert neighbors == []


async def test_matches_unknown_id_404(client):
    res = await client.get("/v1/overseas/999999/matches")
    assert res.status_code == 404 and res.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


async def test_matches_without_embedding_returns_empty(client, seeded_overseas_no_embedding):
    res = await client.get(f"/v1/overseas/{seeded_overseas_no_embedding}/matches")
    assert res.json()["data"]["matches"] == []


def _match_row(cpyrht_div_cd: str | None) -> matching.MatchRow:
    return matching.MatchRow(
        content_id="1",
        title="t",
        region_label="강원",
        image_url="https://tong.visitkorea.or.kr/cms/resource/98/3045598_image2_1.jpg",
        overview_first=None,
        cpyrht_div_cd=cpyrht_div_cd,
    )


def test_display_image_url_type1_is_tile_sized(monkeypatch) -> None:
    """62pt 타일에 1620px 을 내리면 슬라이드 하나가 1MB 를 넘는다."""
    monkeypatch.setattr(settings, "IMG_PROXY_T1_SECRET", "s3cret")
    url = matching.display_image_url(_match_row("Type1"))
    assert url.startswith("https://img.pictrip.org/t1/320/")
    assert url.endswith("/tong.visitkorea.or.kr/cms/resource/98/3045598_image1_1.jpg")


def test_display_image_url_type3_and_unknown_pass_through(monkeypatch) -> None:
    monkeypatch.setattr(settings, "IMG_PROXY_T1_SECRET", "s3cret")
    raw = "https://tong.visitkorea.or.kr/cms/resource/98/3045598_image2_1.jpg"
    assert matching.display_image_url(_match_row("Type3")) == raw
    assert matching.display_image_url(_match_row(None)) == raw


def test_display_image_url_without_secret_passes_through(monkeypatch) -> None:
    monkeypatch.setattr(settings, "IMG_PROXY_T1_SECRET", "")
    raw = "https://tong.visitkorea.or.kr/cms/resource/98/3045598_image2_1.jpg"
    assert matching.display_image_url(_match_row("Type1")) == raw
