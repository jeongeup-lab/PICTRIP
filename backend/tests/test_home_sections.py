from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import date

import pytest
import pytest_asyncio
from fakeredis.aioredis import FakeRedis
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.core.redis import get_redis
from app.kto.client import get_kto
from app.main import app
from app.modules.feed.services import curation
from app.security.jwt import create_access_token

LAT, LNG = 35.15, 129.05
EMBEDDING_DIM = 512


@pytest_asyncio.fixture(autouse=True)
async def seeded(request: pytest_asyncio.plugin.SubRequest) -> AsyncIterator[AsyncSession]:
    from app.core.db import get_db

    eng = create_async_engine(str(settings.sqlalchemy_database_url), poolclass=NullPool)
    async with eng.connect() as conn:
        tx = await conn.begin()
        try:
            seed = AsyncSession(
                bind=conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
            )

            async def _override() -> AsyncIterator[AsyncSession]:
                session = AsyncSession(
                    bind=conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
                )
                try:
                    yield session
                finally:
                    await session.close()

            app.dependency_overrides[get_db] = _override
            app.dependency_overrides[get_redis] = lambda: FakeRedis(decode_responses=True)
            app.dependency_overrides[get_kto] = lambda: None
            try:
                yield seed
            finally:
                await seed.close()
                app.dependency_overrides.clear()
        finally:
            if tx.is_active:
                await tx.rollback()
    await eng.dispose()


async def _seed_region(session: AsyncSession) -> None:
    await session.execute(
        text(
            "INSERT INTO regions (ldong_regn_cd, ldong_regn_nm) VALUES ('26', '부산광역시') "
            "ON CONFLICT DO NOTHING"
        )
    )
    for code, name in (("26380", "사하구"), ("26440", "강서구")):
        await session.execute(
            text(
                "INSERT INTO sigungus (ldong_signgu_cd, ldong_regn_cd, ldong_signgu_nm) "
                "VALUES (:c, '26', :n) ON CONFLICT DO NOTHING"
            ),
            {"c": code, "n": name},
        )
    await session.execute(
        text(
            "INSERT INTO lcls_systm_codes (lcls_systm3_cd, lcls_systm3_nm) "
            "VALUES ('NA010100', '자연관광지') ON CONFLICT DO NOTHING"
        )
    )


async def _seed_spot(
    session: AsyncSession,
    cid: str,
    *,
    lat: float = LAT,
    lng: float = LNG,
    signgu: str = "26380",
    lcls3: str = "NA010100",
    title: str | None = None,
) -> None:
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, first_image_url, show_flag, "
            "mapx, mapy, lcls_systm1, lcls_systm3, ldong_regn_cd, ldong_signgu_cd) "
            "VALUES (:cid, 12, :t, 'http://tong.visitkorea.or.kr/i.jpg', 1, :lng, :lat, 'NA', "
            ":l3, '26', :sg) ON CONFLICT (content_id) DO NOTHING"
        ),
        {
            "cid": cid,
            "t": title or f"스팟-{cid}",
            "lng": lng,
            "lat": lat,
            "sg": signgu,
            "l3": lcls3,
        },
    )


async def _seed_program_region(session: AsyncSession) -> str:
    program = curation.PROGRAMS[0]
    await session.execute(
        text(
            "INSERT INTO sigungus (ldong_signgu_cd, ldong_regn_cd, ldong_signgu_nm) "
            "VALUES ('26999', '26', :n) ON CONFLICT DO NOTHING"
        ),
        {"n": program.sigungu},
    )
    return "26999"


async def _seed_food(session: AsyncSession, cid: str, *, cafe: bool = False) -> None:
    await session.execute(
        text(
            "UPDATE spots SET lcls_systm1 = 'FD', lcls_systm2 = :l2, lcls_systm3 = NULL "
            "WHERE content_id = :cid"
        ),
        {"cid": cid, "l2": "FD05" if cafe else "FD01"},
    )


async def _seed_visual(session: AsyncSession, cid: str, *, score: float = 0.1) -> None:
    await session.execute(
        text(
            "INSERT INTO spot_visual (content_id, photo_type, aesthetic_score) "
            "VALUES (:cid, 'view', :sc) ON CONFLICT (content_id) DO NOTHING"
        ),
        {"cid": cid, "sc": score},
    )


async def _seed_buzz(
    session: AsyncSession, cid: str, *, recent: float = 1.0, blog_total: int = 5000
) -> None:
    await session.execute(
        text(
            "INSERT INTO spot_buzz "
            "(content_id, scope, mentions, distinct_blogs, recent_ratio, blog_total) "
            "VALUES (:cid, 'base', 0, 0, :r, :t) ON CONFLICT DO NOTHING"
        ),
        {"cid": cid, "r": recent, "t": blog_total},
    )


async def _seed_rate(
    session: AsyncSession, cid: str, rate: str, *, base_ymd: str = "2026-07-01"
) -> None:
    await session.execute(
        text(
            "INSERT INTO spot_concentration (content_id, concentration_rate, base_ymd, raw_name) "
            "VALUES (:cid, :rate, :ymd, :rn) ON CONFLICT (content_id) DO NOTHING"
        ),
        {"cid": cid, "rate": rate, "rn": f"n-{cid}", "ymd": date.fromisoformat(base_ymd)},
    )


def _vector(*, axis: int) -> str:
    values = ["0.0"] * EMBEDDING_DIM
    values[axis] = "1.0"
    return "[" + ",".join(values) + "]"


async def _seed_embedding(session: AsyncSession, cid: str, *, axis: int) -> None:
    await session.execute(
        text(
            "INSERT INTO spot_embeddings (content_id, image_url, embedding) "
            "VALUES (:cid, 'http://tong.visitkorea.or.kr/i.jpg', CAST(:v AS halfvec(512))) "
            "ON CONFLICT (content_id) DO NOTHING"
        ),
        {"cid": cid, "v": _vector(axis=axis)},
    )


async def _seed_user(session: AsyncSession) -> int:
    row = (
        await session.execute(
            text("INSERT INTO users (email, name) VALUES (:e, '이신성') RETURNING id"),
            {"e": f"home-{uuid.uuid4().hex[:10]}@e.st"},
        )
    ).first()
    assert row is not None
    return int(row.id)


async def _save(session: AsyncSession, *, user_id: int, cid: str) -> None:
    await session.execute(
        text(
            "INSERT INTO user_saved_spots (user_id, content_id) VALUES (:u, :c) "
            "ON CONFLICT DO NOTHING"
        ),
        {"u": user_id, "c": cid},
    )


def _auth(user_id: int) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id=user_id)}"}


async def test_nearby_ranks_by_concentration_before_distance(
    client: AsyncClient, seeded: AsyncSession
) -> None:
    await _seed_region(seeded)
    await _seed_spot(seeded, "near-far", lat=LAT + 0.02, lng=LNG)
    await _seed_spot(seeded, "near-close", lat=LAT + 0.001, lng=LNG)
    await _seed_rate(seeded, "near-far", "90.00")
    await _seed_rate(seeded, "near-close", "10.00")
    await seeded.commit()

    res = await client.get("/v1/home/nearby", params={"lat": LAT, "lng": LNG, "limit": 20})
    assert res.status_code == 200
    items = res.json()["data"]["items"]
    ids = [i["contentId"] for i in items]
    assert ids.index("near-far") < ids.index("near-close")

    top = next(i for i in items if i["contentId"] == "near-far")
    assert top["rank"] == 1
    assert top["dist"] is not None and top["dist"] > 0
    assert top["regionLabel"] == "부산광역시 사하구"
    assert top["tag"] == "자연관광지"


async def test_nearby_excludes_spots_outside_the_radius(
    client: AsyncClient, seeded: AsyncSession
) -> None:
    await _seed_region(seeded)
    await _seed_spot(seeded, "far-away", lat=LAT + 1.0, lng=LNG)
    await seeded.commit()

    res = await client.get("/v1/home/nearby", params={"lat": LAT, "lng": LNG, "limit": 20})
    assert res.status_code == 200
    assert all(i["contentId"] != "far-away" for i in res.json()["data"]["items"])


async def test_nearby_requires_coords(client: AsyncClient, seeded: AsyncSession) -> None:
    res = await client.get("/v1/home/nearby")
    assert res.status_code == 422


async def test_trending_returns_ranked_signal_cards(
    client: AsyncClient, seeded: AsyncSession
) -> None:
    await _seed_region(seeded)
    await seeded.execute(
        text(
            "INSERT INTO regions (ldong_regn_cd, ldong_regn_nm) VALUES ('50', '제주특별자치도') "
            "ON CONFLICT DO NOTHING"
        )
    )
    await _seed_spot(seeded, "trend-hi")
    await _seed_visual(seeded, "trend-hi", score=0.2)
    await _seed_buzz(seeded, "trend-hi", blog_total=9000)
    await _seed_spot(seeded, "trend-lo")
    await seeded.execute(
        text("UPDATE spots SET ldong_regn_cd = '50' WHERE content_id = 'trend-lo'")
    )
    await _seed_visual(seeded, "trend-lo", score=0.05)
    await _seed_buzz(seeded, "trend-lo", recent=0.9, blog_total=600)
    await seeded.commit()

    res = await client.get("/v1/home/trending")
    assert res.status_code == 200
    items = res.json()["data"]["items"]
    assert items[0]["contentId"] == "trend-hi"
    assert {i["contentId"] for i in items} == {"trend-hi", "trend-lo"}
    assert [i["rank"] for i in items] == list(range(1, len(items) + 1))
    assert items[0]["dist"] is None
    assert items[0]["tag"] == "요즘뜨는"


async def test_ranked_sections_expose_the_snapshot_the_cards_came_from(
    client: AsyncClient, seeded: AsyncSession
) -> None:
    await _seed_region(seeded)
    await _seed_spot(seeded, "base-date")
    await _seed_rate(seeded, "base-date", "50.00")
    await seeded.commit()

    trending = await client.get("/v1/home/trending")
    nearby = await client.get("/v1/home/nearby", params={"lat": LAT, "lng": LNG})
    assert trending.json()["data"]["baseDate"] is None
    assert nearby.json()["data"]["baseDate"] == "2026-07-01"


async def test_a_mixed_snapshot_reports_no_base_date(
    client: AsyncClient, seeded: AsyncSession
) -> None:
    await _seed_region(seeded)
    await _seed_spot(seeded, "mixed-old")
    await _seed_spot(seeded, "mixed-new")
    await _seed_rate(seeded, "mixed-old", "90.00", base_ymd="2026-07-01")
    await _seed_rate(seeded, "mixed-new", "80.00", base_ymd="2026-07-02")
    await seeded.commit()

    nearby = await client.get("/v1/home/nearby", params={"lat": LAT, "lng": LNG})
    assert len(nearby.json()["data"]["items"]) >= 2
    assert nearby.json()["data"]["baseDate"] is None


async def test_spots_without_concentration_do_not_erase_the_base_date(
    client: AsyncClient, seeded: AsyncSession
) -> None:
    await _seed_region(seeded)
    await _seed_spot(seeded, "rated")
    await _seed_spot(seeded, "unrated")
    await _seed_rate(seeded, "rated", "70.00")
    await seeded.commit()

    nearby = await client.get("/v1/home/nearby", params={"lat": LAT, "lng": LNG})
    body = nearby.json()["data"]
    assert {i["contentId"] for i in body["items"]} >= {"rated", "unrated"}
    assert body["baseDate"] == "2026-07-01"


async def test_taste_picks_only_returns_spots_with_embeddings(
    client: AsyncClient, seeded: AsyncSession
) -> None:
    await _seed_region(seeded)
    await _seed_spot(seeded, "pick-embedded")
    await _seed_spot(seeded, "pick-bare", signgu="26440")
    await _seed_rate(seeded, "pick-embedded", "80.00")
    await _seed_rate(seeded, "pick-bare", "95.00")
    await _seed_embedding(seeded, "pick-embedded", axis=0)
    await seeded.commit()

    res = await client.get("/v1/home/taste-picks", params={"limit": 30})
    assert res.status_code == 200
    ids = [i["contentId"] for i in res.json()["data"]["items"]]
    assert "pick-embedded" in ids
    assert "pick-bare" not in ids


async def test_recommendations_need_a_minimum_number_of_saves(
    client: AsyncClient, seeded: AsyncSession
) -> None:
    await _seed_region(seeded)
    uid = await _seed_user(seeded)
    await _seed_spot(seeded, "rec-seed-1")
    await _save(seeded, user_id=uid, cid="rec-seed-1")
    await seeded.commit()

    res = await client.get("/v1/home/recommendations", headers=_auth(uid))
    assert res.status_code == 200
    body = res.json()["data"]
    assert body["ready"] is False
    assert body["savedCount"] == 1
    assert body["minSaved"] == 3
    assert body["items"] == []


async def test_recommendations_rank_neighbours_of_the_saved_centroid(
    client: AsyncClient, seeded: AsyncSession
) -> None:
    await _seed_region(seeded)
    uid = await _seed_user(seeded)
    for i in range(3):
        cid = f"rec-seed-{i}"
        await _seed_spot(seeded, cid)
        await _seed_embedding(seeded, cid, axis=0)
        await _save(seeded, user_id=uid, cid=cid)
    await _seed_spot(seeded, "rec-hit")
    await _seed_embedding(seeded, "rec-hit", axis=0)
    await _seed_spot(seeded, "rec-miss")
    await _seed_embedding(seeded, "rec-miss", axis=7)
    await seeded.commit()

    res = await client.get(
        "/v1/home/recommendations", params={"lat": LAT, "lng": LNG}, headers=_auth(uid)
    )
    assert res.status_code == 200
    body = res.json()["data"]
    assert body["ready"] is True
    ids = [i["contentId"] for i in body["items"]]
    assert ids[0] == "rec-hit"
    assert not any(i.startswith("rec-seed") for i in ids)

    hit = body["items"][0]
    assert hit["anchorTitle"] in {f"스팟-rec-seed-{i}" for i in range(3)}
    assert hit["dist"] is not None
    assert hit["category"] == "자연관광지"


async def test_recommendations_require_authentication(
    client: AsyncClient, seeded: AsyncSession
) -> None:
    res = await client.get("/v1/home/recommendations")
    assert res.status_code == 401


async def test_around_and_hot_channels_are_gone(client: AsyncClient, seeded: AsyncSession) -> None:
    for key in ("around", "hot"):
        res = await client.get(f"/v1/home/channels/{key}", params={"lat": LAT, "lng": LNG})
        assert res.status_code == 404
        assert res.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


async def test_nearby_category_filter_returns_only_that_pool(
    client: AsyncClient, seeded: AsyncSession
) -> None:
    await _seed_region(seeded)
    await _seed_spot(seeded, "flt-spot")
    await _seed_spot(seeded, "flt-cafe")
    await seeded.execute(
        text(
            "UPDATE spots SET lcls_systm1 = 'FD', lcls_systm2 = 'FD05', lcls_systm3 = NULL "
            "WHERE content_id = 'flt-cafe'"
        )
    )
    await seeded.commit()

    res = await client.get("/v1/home/nearby", params={"lat": LAT, "lng": LNG, "category": "CAFE"})
    assert res.status_code == 200
    ids = [i["contentId"] for i in res.json()["data"]["items"]]
    assert ids == ["flt-cafe"]

    res = await client.get("/v1/home/nearby", params={"lat": LAT, "lng": LNG, "category": "SPOT"})
    ids = [i["contentId"] for i in res.json()["data"]["items"]]
    assert ids == ["flt-spot"]


async def test_trending_category_filter_serves_the_signal_pool(
    client: AsyncClient, seeded: AsyncSession
) -> None:
    await _seed_region(seeded)
    await _seed_spot(seeded, "flt-hi")
    await _seed_visual(seeded, "flt-hi", score=0.2)
    await _seed_buzz(seeded, "flt-hi", blog_total=9000)
    await seeded.commit()

    res = await client.get("/v1/home/trending", params={"category": "SPOT"})
    assert res.status_code == 200
    items = res.json()["data"]["items"]
    assert [i["contentId"] for i in items] == ["flt-hi"]
    assert items[0]["tag"] == "요즘뜨는"

    res = await client.get("/v1/home/trending", params={"category": "CAFE"})
    assert res.json()["data"]["items"] == []


async def test_rank_category_rejects_unknown_values(
    client: AsyncClient, seeded: AsyncSession
) -> None:
    res = await client.get("/v1/home/nearby", params={"lat": LAT, "lng": LNG, "category": "PETS"})
    assert res.status_code == 422


async def test_nearby_cards_carry_coordinates_for_the_home_map(
    client: AsyncClient, seeded: AsyncSession
) -> None:
    await _seed_region(seeded)
    await _seed_spot(seeded, "coord-one", lat=LAT + 0.001, lng=LNG + 0.002)
    await seeded.commit()

    res = await client.get("/v1/home/nearby", params={"lat": LAT, "lng": LNG, "limit": 20})
    assert res.status_code == 200
    card = next(i for i in res.json()["data"]["items"] if i["contentId"] == "coord-one")
    assert card["lat"] == pytest.approx(LAT + 0.001, abs=1e-6)
    assert card["lng"] == pytest.approx(LNG + 0.002, abs=1e-6)


async def test_curation_lays_the_region_out_as_a_course(
    client: AsyncClient, seeded: AsyncSession
) -> None:
    await _seed_region(seeded)
    sg = await _seed_program_region(seeded)
    for cid, score in (("see-1", 0.9), ("see-2", 0.8), ("see-3", 0.1)):
        await _seed_spot(seeded, cid, signgu=sg, title=f"명소 {cid}")
        await _seed_visual(seeded, cid, score=score)
    for cid, score in (("eat-1", 0.9), ("eat-2", 0.8), ("eat-3", 0.1)):
        await _seed_spot(seeded, cid, signgu=sg, title=f"맛집 {cid}")
        await _seed_food(seeded, cid)
        await _seed_visual(seeded, cid, score=score)
    for cid, score in (("cup-1", 0.9), ("cup-2", 0.8), ("cup-3", 0.1)):
        await _seed_spot(seeded, cid, signgu=sg, title=f"카페 {cid}")
        await _seed_food(seeded, cid, cafe=True)
        await _seed_visual(seeded, cid, score=score)
    await seeded.commit()

    res = await client.get("/v1/home/curation")
    assert res.status_code == 200
    body = res.json()["data"]
    program = curation.PROGRAMS[0]

    assert [i["contentId"] for i in body["items"]] == [
        "see-1",
        "see-2",
        "eat-1",
        "eat-2",
        "cup-1",
        "cup-2",
    ]
    assert body["kicker"] == curation.KICKER
    assert body["title"] == program.title
    assert body["subtitle"] == f"{program.sigungu} 6곳. {program.lead}"


async def test_curation_skips_spots_outside_the_programmed_region(
    client: AsyncClient, seeded: AsyncSession
) -> None:
    await _seed_region(seeded)
    sg = await _seed_program_region(seeded)
    await _seed_spot(seeded, "inside", signgu=sg, title="안쪽")
    await _seed_visual(seeded, "inside", score=0.5)
    await _seed_spot(seeded, "outside", signgu="26380", title="바깥")
    await _seed_visual(seeded, "outside", score=0.9)
    await seeded.commit()

    res = await client.get("/v1/home/curation")
    ids = [i["contentId"] for i in res.json()["data"]["items"]]
    assert ids == ["inside"]


async def test_curation_reports_what_it_actually_found(
    client: AsyncClient, seeded: AsyncSession
) -> None:
    await _seed_region(seeded)
    sg = await _seed_program_region(seeded)
    await _seed_spot(seeded, "lonely", signgu=sg, title="한 곳뿐")
    await _seed_visual(seeded, "lonely", score=0.5)
    await seeded.commit()

    res = await client.get("/v1/home/curation")
    body = res.json()["data"]
    program = curation.PROGRAMS[0]
    assert len(body["items"]) == 1
    assert body["subtitle"] == f"{program.sigungu} 1곳. {program.lead}"


def test_every_program_asks_for_six_places() -> None:
    for program in curation.PROGRAMS:
        assert program.size == 6, program.sigungu
        assert program.sigungu.strip() == program.sigungu
        assert program.title and program.lead
