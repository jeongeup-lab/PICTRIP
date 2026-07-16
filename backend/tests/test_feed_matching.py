from __future__ import annotations

import json
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


@dataclass
class Seeded:
    overseas_id: int


@pytest.fixture
async def seeded_matching(db_session) -> Seeded:
    oid = await _insert_overseas(db_session, embedding=_CLOSE)
    await _insert_spot(db_session, "mt_a", _CLOSE, overview="첫 문장이다. 둘째 문장.")
    await _insert_spot(db_session, "mt_b", _CLOSE, overview="다른 소개문이다.")
    return Seeded(overseas_id=oid)


@pytest.fixture
async def seeded_matching_far(db_session) -> Seeded:
    oid = await _insert_overseas(db_session, embedding=_CLOSE)
    await _insert_spot(db_session, "mt_far_a", _FAR, overview="멀리 있다.")
    await _insert_spot(db_session, "mt_far_b", _FAR, overview="멀리 있다 둘.")
    return Seeded(overseas_id=oid)


@pytest.fixture
async def seeded_overseas_no_embedding(db_session) -> int:
    return await _insert_overseas(db_session, embedding=None)


async def test_matches_returns_similar_domestic(client, seeded_matching):
    res = await client.get(f"/v1/overseas/{seeded_matching.overseas_id}/matches")
    body = res.json()
    assert res.status_code == 200 and body["error"] is None
    matches = body["data"]["matches"]
    assert 1 <= len(matches) <= 3
    assert {"contentId", "title", "regionLabel", "imageUrl", "overviewFirst"} <= set(matches[0])


async def test_matches_threshold_filters_far_spots(client, seeded_matching_far):
    res = await client.get(f"/v1/overseas/{seeded_matching_far.overseas_id}/matches")
    content_ids = {row["contentId"] for row in res.json()["data"]["matches"]}
    assert content_ids.isdisjoint({"mt_far_a", "mt_far_b"})


async def test_matches_cached_in_redis(client, seeded_matching, redis_client_fake):
    await client.get(f"/v1/overseas/{seeded_matching.overseas_id}/matches")
    assert await redis_client_fake.get(f"match:0:{seeded_matching.overseas_id}") is not None


async def test_stale_cached_match_is_recomputed(
    client, db_session, seeded_matching, redis_client_fake
):
    first = await client.get(f"/v1/overseas/{seeded_matching.overseas_id}/matches")
    cached_ids = {row["contentId"] for row in first.json()["data"]["matches"]}
    stale_id = next(iter(cached_ids))
    await db_session.execute(
        text(
            "UPDATE spots SET first_image_url = 'http://kto/replaced.jpg' WHERE content_id = :cid"
        ),
        {"cid": stale_id},
    )
    await db_session.commit()

    refreshed = await client.get(f"/v1/overseas/{seeded_matching.overseas_id}/matches")

    refreshed_ids = {row["contentId"] for row in refreshed.json()["data"]["matches"]}
    assert stale_id not in refreshed_ids
    assert await redis_client_fake.get("matching:revision") == "1"
    assert await redis_client_fake.get(f"match:1:{seeded_matching.overseas_id}") is not None


async def test_cached_match_is_hidden_when_overseas_embedding_becomes_invalid(
    client, db_session, seeded_matching, redis_client_fake
):
    first = await client.get(f"/v1/overseas/{seeded_matching.overseas_id}/matches")
    assert first.json()["data"]["matches"]
    await db_session.execute(
        text(
            "UPDATE overseas_spots SET image_url = 'https://img/replaced', embedding = NULL "
            "WHERE id = :oid"
        ),
        {"oid": seeded_matching.overseas_id},
    )
    await db_session.commit()

    refreshed = await client.get(f"/v1/overseas/{seeded_matching.overseas_id}/matches")

    assert refreshed.status_code == 200
    assert refreshed.json()["data"]["matches"] == []
    assert await redis_client_fake.get("matching:revision") == "1"
    assert await redis_client_fake.get(f"match:0:{seeded_matching.overseas_id}") is not None
    assert await redis_client_fake.get(f"match:1:{seeded_matching.overseas_id}") is None


async def test_source_change_between_neighbor_search_and_hydration_is_filtered(
    client,
    db_session,
    seeded_matching,
    redis_client_fake,
    monkeypatch: pytest.MonkeyPatch,
):
    await _insert_spot(db_session, "mt_race_c", _CLOSE, overview=None)
    await _insert_spot(db_session, "mt_race_d", _CLOSE, overview=None)
    original_hydrate = matching._hydrate
    changed_content_id: str | None = None

    async def change_then_hydrate(session, candidate_ids, source_by_id):
        nonlocal changed_content_id
        changed_content_id = candidate_ids[0]
        await session.execute(
            text(
                "UPDATE spots SET first_image_url = 'http://kto/raced.jpg' WHERE content_id = :cid"
            ),
            {"cid": changed_content_id},
        )
        await session.flush()
        return await original_hydrate(session, candidate_ids, source_by_id)

    monkeypatch.setattr(matching, "_hydrate", change_then_hydrate)

    response = await client.get(f"/v1/overseas/{seeded_matching.overseas_id}/matches")

    content_ids = {row["contentId"] for row in response.json()["data"]["matches"]}
    assert response.status_code == 200
    assert changed_content_id is not None
    assert changed_content_id not in content_ids
    assert len(content_ids) == 3
    assert await redis_client_fake.get("matching:revision") == "1"


async def test_source_change_after_hydration_backfills_from_remaining_candidates(
    client,
    db_session,
    seeded_matching,
    redis_client_fake,
    monkeypatch: pytest.MonkeyPatch,
):
    await _insert_spot(db_session, "mt_late_race_c", _CLOSE, overview=None)
    await _insert_spot(db_session, "mt_late_race_d", _CLOSE, overview=None)
    original_get_state = matching.repositories.get_cached_match_state
    changed_content_id: str | None = None

    async def change_then_get_state(session, overseas_id, content_ids):
        nonlocal changed_content_id
        changed_content_id = content_ids[0]
        await session.execute(
            text(
                "UPDATE spots SET first_image_url = 'http://kto/late-raced.jpg' "
                "WHERE content_id = :cid"
            ),
            {"cid": changed_content_id},
        )
        await session.flush()
        return await original_get_state(session, overseas_id, content_ids)

    monkeypatch.setattr(matching.repositories, "get_cached_match_state", change_then_get_state)

    response = await client.get(f"/v1/overseas/{seeded_matching.overseas_id}/matches")

    matches = response.json()["data"]["matches"]
    content_ids = {row["contentId"] for row in matches}
    cached = await redis_client_fake.get(f"match:1:{seeded_matching.overseas_id}")
    assert response.status_code == 200
    assert changed_content_id is not None
    assert changed_content_id not in content_ids
    assert len(content_ids) == 3
    assert cached is not None
    assert len(json.loads(cached)) == 3


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


async def test_cached_match_state_drops_non_attraction_spot(db_session):
    oid = await _insert_overseas(db_session, embedding=_CLOSE)
    await _insert_spot(db_session, "mt_state_attr", _CLOSE, overview=None, lcls1="NA")
    await _insert_spot(db_session, "mt_state_shop", _CLOSE, overview=None, lcls1="SH")

    state = await repositories.get_cached_match_state(
        db_session, oid, ["mt_state_attr", "mt_state_shop"]
    )

    assert state is not None
    _has_embedding, current = state
    assert "mt_state_attr" in current
    assert "mt_state_shop" not in current


async def test_cached_match_state_drops_uncategorized_spot(db_session):
    oid = await _insert_overseas(db_session, embedding=_CLOSE)
    await _insert_spot(db_session, "mt_state_cat", _CLOSE, overview=None, lcls1="NA")
    await _insert_spot(db_session, "mt_state_uncat", _CLOSE, overview=None, lcls1=None)

    state = await repositories.get_cached_match_state(
        db_session, oid, ["mt_state_cat", "mt_state_uncat"]
    )

    assert state is not None
    _has_embedding, current = state
    assert "mt_state_cat" in current
    assert "mt_state_uncat" not in current


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


def test_display_image_url_type1_returns_signed_transform(monkeypatch) -> None:
    monkeypatch.setattr(settings, "IMG_PROXY_T1_SECRET", "s3cret")
    url = matching.display_image_url(_match_row("Type1"))
    assert url.startswith("https://img.pictrip.org/t1/1620/")
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
