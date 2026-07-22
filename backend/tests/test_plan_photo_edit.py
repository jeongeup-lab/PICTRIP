from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.kto import display
from app.main import app
from app.modules.plan.errors import (
    PlanNotEnoughSpots,
    PlanSlotInvalid,
    PlanSpotNotFound,
)
from app.modules.plan.schemas import (
    AssembleRequest,
    ExtractedPlace,
    FromSpotRequest,
    PlanEditRequest,
    ResolvedPlace,
    ResolvedSpot,
)
from app.modules.plan.services import assemble, chains, edit, ingest, photo, seed
from app.web.errors import ImageInvalid

_DIM = 512
_CLOSE = [0.1] * _DIM
_FAR = [0.1 if i % 2 == 0 else -0.1 for i in range(_DIM)]


def _literal(vec: list[float]) -> str:
    return "[" + ",".join(f"{v:.6f}" for v in vec) + "]"


async def _insert_spot(
    session: AsyncSession,
    content_id: str,
    *,
    lat: float = 37.0,
    lng: float = 127.0,
    lcls1: str | None = "NA",
    lcls2: str | None = None,
    ctype: int = 12,
    vec: list[float] | None = None,
) -> None:
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, first_image_url, "
            "addr1, mapx, mapy, show_flag, lcls_systm1, lcls_systm2) "
            "VALUES (:cid, :ctype, :t, 'http://kto/p.jpg', '전라남도 여수시', :lng, :lat, 1, "
            ":lcls1, :lcls2) ON CONFLICT (content_id) DO NOTHING"
        ),
        {
            "cid": content_id,
            "t": f"title-{content_id}",
            "lat": lat,
            "lng": lng,
            "lcls1": lcls1,
            "lcls2": lcls2,
            "ctype": ctype,
        },
    )
    if vec is not None:
        await session.execute(
            text(
                "INSERT INTO spot_embeddings (content_id, embedding, image_url) "
                "VALUES (:cid, CAST(:emb AS halfvec(512)), 'http://kto/p.jpg') "
                "ON CONFLICT (content_id) DO NOTHING"
            ),
            {"cid": content_id, "emb": _literal(vec)},
        )
    await session.commit()


async def test_photo_match_orders_by_similarity(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _insert_spot(db_session, "pm-close", vec=_CLOSE)
    await _insert_spot(db_session, "pm-far", vec=_FAR)
    monkeypatch.setattr(photo.embedder, "embed_image", lambda b: _CLOSE)

    result = await photo.match_photo(db_session, image_bytes=b"img", image_mime="image/jpeg")

    ids = [m.contentId for m in result.matches]
    assert ids.index("pm-close") < ids.index("pm-far")
    top = result.matches[0]
    assert top.similarity > result.matches[-1].similarity
    assert top.imageUrl == "http://kto/p.jpg"
    assert 0.0 <= top.similarity <= 1.0


async def test_photo_match_rejects_bad_image(db_session: AsyncSession) -> None:
    with pytest.raises(ImageInvalid):
        await photo.match_photo(db_session, image_bytes=b"", image_mime="image/jpeg")
    with pytest.raises(ImageInvalid):
        await photo.match_photo(db_session, image_bytes=b"gif", image_mime="image/gif")


async def test_photo_match_route_requires_multipart(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        resp = await client.post("/v1/plan/photo-match", json={})
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "PLAN_SOURCE_INVALID"


async def test_photo_match_route_rejects_oversized_upload(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    app.dependency_overrides[get_db] = lambda: db_session
    oversized = b"x" * (ingest.MAX_IMAGE_BYTES + 1024)
    try:
        resp = await client.post(
            "/v1/plan/photo-match",
            files={"image": ("big.jpg", oversized, "image/jpeg")},
        )
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "IMAGE_INVALID"


async def test_from_spot_issues_images_through_copyright_seam(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(display.settings, "IMG_PROXY_T1_SECRET", "s3cret")
    monkeypatch.setattr(display.settings, "IMG_PROXY_ORIGIN", "https://img.pictrip.org")
    await _insert_spot(db_session, "cp-seed", lat=37.0, lng=127.0)
    await _insert_spot(db_session, "cp-food", lat=37.004, lng=127.0, lcls1="FD", lcls2="FD01")
    await db_session.execute(
        text(
            "UPDATE spots SET first_image_url = 'http://tong.visitkorea.or.kr/a_image2_1.jpg', "
            "cpyrht_div_cd = CASE content_id WHEN 'cp-seed' THEN 'Type1' ELSE 'Type3' END "
            "WHERE content_id IN ('cp-seed', 'cp-food')"
        )
    )
    await db_session.commit()

    response = await seed.build_from_spot(db_session, FromSpotRequest(contentId="cp-seed", days=1))
    urls = {
        slot.place.spot.contentId: slot.place.spot.imageUrl
        for day in response.days
        for slot in day.slots
        if slot.place.spot is not None
    }

    assert urls["cp-seed"].startswith("https://img.pictrip.org")
    assert urls["cp-food"] == "https://tong.visitkorea.or.kr/a_image2_1.jpg"


async def test_from_spot_builds_plan(db_session: AsyncSession) -> None:
    await _insert_spot(db_session, "fs-seed", lat=37.0, lng=127.0)
    await _insert_spot(db_session, "fs-attr1", lat=37.001, lng=127.0)
    await _insert_spot(db_session, "fs-attr2", lat=37.002, lng=127.0)
    await _insert_spot(db_session, "fs-food", lat=37.001, lng=127.001, lcls1="FD", lcls2="FD01")
    await _insert_spot(db_session, "fs-cafe", lat=37.002, lng=127.001, lcls1="FD", lcls2="FD05")

    response = await seed.build_from_spot(db_session, FromSpotRequest(contentId="fs-seed", days=1))

    assert response.planId is not None
    assert len(response.days) == 1
    ids = {
        slot.place.spot.contentId for slot in response.days[0].slots if slot.place.spot is not None
    }
    assert {"fs-seed", "fs-food", "fs-cafe"} <= ids
    assert response.sourceTitle == "여수 당일 코스"

    loaded = await assemble.load_plan(db_session, response.planId)
    assert len(loaded.days) == 1


async def _insert_concentration(session: AsyncSession, content_id: str, rate: float) -> None:
    await session.execute(
        text(
            "INSERT INTO spot_concentration (content_id, concentration_rate, base_ymd, raw_name) "
            "VALUES (:cid, :rate, '2026-06-06', :name) ON CONFLICT (content_id) DO NOTHING"
        ),
        {"cid": content_id, "rate": rate, "name": f"raw-{content_id}"},
    )
    await session.commit()


async def _from_spot_ids(session: AsyncSession, seed_id: str, *, days: int = 1) -> set[str]:
    return set(await _from_spot_picks(session, seed_id, days=days))


async def _from_spot_picks(session: AsyncSession, seed_id: str, *, days: int = 1) -> list[str]:
    response = await seed.build_from_spot(session, FromSpotRequest(contentId=seed_id, days=days))
    places = [
        slot.place for day in response.days for slot in day.slots if slot.place.spot is not None
    ]
    places.sort(key=lambda p: p.extracted.orderHint or 0)
    return [p.spot.contentId for p in places if p.spot is not None and p.spot.contentId]


def test_popularity_score_trades_distance_for_popularity() -> None:
    near_unranked = seed.popularity_score(500.0, None)
    far_popular = seed.popularity_score(2_000.0, 95.0)
    assert far_popular < near_unranked
    assert seed.popularity_score(1_000.0, 100.0) == pytest.approx(1.0 - seed.POPULARITY_MAX_KM)


async def test_from_spot_excludes_lodging(db_session: AsyncSession) -> None:
    await _insert_spot(db_session, "lg-seed", lat=37.0, lng=127.0)
    await _insert_spot(
        db_session, "lg-hotel", lat=37.005, lng=127.0, lcls1="VE", lcls2="VE05", ctype=32
    )
    await _insert_spot(db_session, "lg-food", lat=37.001, lng=127.001, lcls1="FD", lcls2="FD01")

    ids = await _from_spot_ids(db_session, "lg-seed")

    assert "lg-hotel" not in ids
    assert {"lg-seed", "lg-food"} <= ids


async def test_from_spot_prefers_popular_over_merely_close(db_session: AsyncSession) -> None:
    await _insert_spot(db_session, "pp-seed", lat=37.0, lng=127.0)
    await _insert_spot(db_session, "pp-noise", lat=37.005, lng=127.0)
    await _insert_spot(db_session, "pp-popular", lat=37.02, lng=127.0)
    await _insert_concentration(db_session, "pp-popular", 95.0)
    await _insert_spot(db_session, "pp-food", lat=37.001, lng=127.001, lcls1="FD", lcls2="FD01")
    await _insert_spot(db_session, "pp-cafe", lat=37.002, lng=127.001, lcls1="FD", lcls2="FD05")

    picks = await _from_spot_picks(db_session, "pp-seed")

    assert picks.index("pp-popular") < picks.index("pp-noise")


async def test_from_spot_skips_near_duplicate_of_picked_spot(db_session: AsyncSession) -> None:
    await _insert_spot(db_session, "nd-seed", lat=37.0, lng=127.0)
    await _insert_spot(db_session, "nd-twin", lat=37.002, lng=127.0)
    await _insert_spot(db_session, "nd-far", lat=37.01, lng=127.0)
    await _insert_spot(db_session, "nd-food", lat=37.001, lng=127.001, lcls1="FD", lcls2="FD01")
    await _insert_spot(db_session, "nd-cafe", lat=37.002, lng=127.001, lcls1="FD", lcls2="FD05")

    ids = await _from_spot_ids(db_session, "nd-seed")

    assert "nd-twin" not in ids
    assert {"nd-seed", "nd-far"} <= ids


async def test_from_spot_keeps_meal_near_attraction(db_session: AsyncSession) -> None:
    await _insert_spot(db_session, "mn-seed", lat=37.0, lng=127.0)
    await _insert_spot(db_session, "mn-food", lat=37.0005, lng=127.0, lcls1="FD", lcls2="FD01")

    ids = await _from_spot_ids(db_session, "mn-seed")

    assert {"mn-seed", "mn-food"} <= ids


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("스타벅스 강릉강문해변점", True),
        ("빽다방 포남점", True),
        ("바다김밥 돌산직영점", True),
        ("순두부젤라또 2호점", True),
        ("촌골닭갈비 본점", False),
        ("화복반점", False),
        ("보영반점", False),
        ("백촌막국수", False),
        ("카페 라피끄", False),
        ("", False),
    ],
)
def test_is_chain_branch(title: str, expected: bool) -> None:
    assert chains.is_chain_branch(title) is expected


async def test_from_spot_excludes_chain_branch(db_session: AsyncSession) -> None:
    await _insert_spot(db_session, "cb-seed", lat=37.0, lng=127.0)
    await _insert_spot(db_session, "cb-food", lat=37.004, lng=127.0, lcls1="FD", lcls2="FD01")
    await db_session.execute(
        text("UPDATE spots SET title = '빽다방 포남점' WHERE content_id = 'cb-food'")
    )
    await _insert_spot(db_session, "cb-local", lat=37.006, lng=127.0, lcls1="FD", lcls2="FD01")
    await db_session.commit()

    ids = await _from_spot_ids(db_session, "cb-seed")

    assert "cb-food" not in ids
    assert {"cb-seed", "cb-local"} <= ids


async def test_from_spot_unknown_spot(db_session: AsyncSession) -> None:
    with pytest.raises(PlanSpotNotFound):
        await seed.build_from_spot(db_session, FromSpotRequest(contentId="fs-none", days=1))


async def test_from_spot_not_enough_spots(db_session: AsyncSession) -> None:
    await _insert_spot(db_session, "fs-alone", lat=35.0, lng=128.0)
    with pytest.raises(PlanNotEnoughSpots):
        await seed.build_from_spot(db_session, FromSpotRequest(contentId="fs-alone", days=2))


def _place(name: str, content_id: str, order: int, *, lat: float, lng: float) -> ResolvedPlace:
    return ResolvedPlace(
        extracted=ExtractedPlace(name=name, placeType="attraction", orderHint=order),
        spot=ResolvedSpot(
            contentId=content_id,
            title=name,
            address="전라남도 여수시",
            lat=lat,
            lng=lng,
        ),
        confidence=1.0,
        status="matched",
    )


async def _build_plan(db_session: AsyncSession, count: int, *, days: int = 1) -> str:
    places = [
        _place(f"장소{i}", f"pl-{i}", i, lat=37.0 + i * 0.001, lng=127.0)
        for i in range(1, count + 1)
    ]
    response = await assemble.build_schedule(
        db_session, AssembleRequest(places=places, days=days, sourceKind="text")
    )
    assert response.planId is not None
    return response.planId


async def test_alternatives_excludes_plan_members(db_session: AsyncSession) -> None:
    plan_id = await _build_plan(db_session, 2)
    await _insert_spot(db_session, "pl-1", lat=37.001, lng=127.0)
    await _insert_spot(db_session, "alt-1", lat=37.0015, lng=127.0)
    await _insert_spot(db_session, "alt-2", lat=37.0016, lng=127.0)

    result = await edit.list_alternatives(db_session, plan_id, day=1, slot=0)

    ids = {alt.contentId for alt in result.alternatives}
    assert ids <= {"alt-1", "alt-2"}
    assert "pl-1" not in ids and "pl-2" not in ids
    assert len(result.alternatives) <= 3


async def test_alternatives_invalid_slot(db_session: AsyncSession) -> None:
    plan_id = await _build_plan(db_session, 2)
    with pytest.raises(PlanSlotInvalid):
        await edit.list_alternatives(db_session, plan_id, day=9, slot=0)


async def test_edit_remove_slot_recomputes_day(db_session: AsyncSession) -> None:
    plan_id = await _build_plan(db_session, 3)

    response = await edit.apply_edit(
        db_session, plan_id, PlanEditRequest(op="remove", day=1, slot=1)
    )

    day = response.days[0]
    assert len(day.slots) == 2
    assert [slot.timeOfDay for slot in day.slots] == ["morning", "afternoon"]
    assert day.slots[0].travelMinutesFromPrev is None
    assert day.slots[1].travelMinutesFromPrev is not None

    loaded = await assemble.load_plan(db_session, plan_id)
    assert len(loaded.days[0].slots) == 2


async def test_edit_remove_last_slot_drops_day(db_session: AsyncSession) -> None:
    plan_id = await _build_plan(db_session, 2, days=2)

    response = await edit.apply_edit(
        db_session, plan_id, PlanEditRequest(op="remove", day=1, slot=0)
    )

    assert len(response.days) == 1
    assert response.days[0].day == 1
    assert len(response.days[0].slots) == 1


async def test_edit_replace_slot(db_session: AsyncSession) -> None:
    plan_id = await _build_plan(db_session, 2)
    await _insert_spot(db_session, "rep-new", lat=37.005, lng=127.0)

    response = await edit.apply_edit(
        db_session, plan_id, PlanEditRequest(op="replace", day=1, slot=0, contentId="rep-new")
    )

    replaced = response.days[0].slots[0].place
    assert replaced.spot is not None and replaced.spot.contentId == "rep-new"
    assert replaced.status == "matched"
    assert replaced.extracted.placeType == "attraction"

    loaded = await assemble.load_plan(db_session, plan_id)
    spot = loaded.days[0].slots[0].place.spot
    assert spot is not None and spot.contentId == "rep-new"


async def test_edit_replace_requires_content_id(db_session: AsyncSession) -> None:
    plan_id = await _build_plan(db_session, 2)
    with pytest.raises(PlanSlotInvalid):
        await edit.apply_edit(db_session, plan_id, PlanEditRequest(op="replace", day=1, slot=0))


async def test_edit_replace_unknown_spot(db_session: AsyncSession) -> None:
    plan_id = await _build_plan(db_session, 2)
    with pytest.raises(PlanSpotNotFound):
        await edit.apply_edit(
            db_session, plan_id, PlanEditRequest(op="replace", day=1, slot=0, contentId="rep-x")
        )
