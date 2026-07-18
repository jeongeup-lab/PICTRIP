from __future__ import annotations

import pytest

from app.modules.plan.naver_local import NaverPlace
from app.modules.plan.services import assemble
from app.modules.plan.services.assemble import assemble_days
from app.modules.plan.services.candidates import PlanCandidates
from app.modules.plan.services.intent import PlanIntent
from app.modules.spots.services import NearbySpotRow
from app.web.errors import PlanNotEnoughSpots

BASE_LAT, BASE_LNG = 37.75, 128.90


def _spot(cid: str, lat: float, lng: float) -> NearbySpotRow:
    return NearbySpotRow(
        content_id=cid,
        title=f"spot-{cid}",
        first_image_url=f"http://kto/{cid}.jpg",
        addr1="강원 강릉시",
        mapx=lng,
        mapy=lat,
        dist=0.0,
        category="관광지",
    )


def _place(name: str, lat: float | None = BASE_LAT, lng: float | None = BASE_LNG) -> NaverPlace:
    return NaverPlace(name=name, category="한식", address="강릉", lat=lat, lng=lng)


def _cand(
    attractions: list[NearbySpotRow],
    meals: list[NaverPlace] | None = None,
    cafes: list[NaverPlace] | None = None,
    food_images: dict[str, str] | None = None,
) -> PlanCandidates:
    return PlanCandidates(
        anchor_lat=BASE_LAT,
        anchor_lng=BASE_LNG,
        attractions=attractions,
        meals=meals or [],
        cafes=cafes or [],
        food_images=food_images or {},
    )


@pytest.fixture(autouse=True)
def _no_odsay(monkeypatch):
    async def _none(**kwargs):
        return None

    monkeypatch.setattr(assemble, "transit_minutes", _none)


async def test_orders_attractions_by_chain_from_anchor():
    far = _spot("far", BASE_LAT + 0.10, BASE_LNG)
    near = _spot("near", BASE_LAT + 0.001, BASE_LNG)
    mid = _spot("mid", BASE_LAT + 0.05, BASE_LNG)

    days = await assemble_days(PlanIntent(region="강릉", days=1), _cand([far, near, mid]))
    names = [s.name for s in days[0].slots if s.type == "attraction"]
    assert names == ["spot-near", "spot-mid"]


async def test_day_slot_labels_and_sources():
    cand = _cand(
        [_spot("a1", BASE_LAT + 0.001, BASE_LNG), _spot("a2", BASE_LAT + 0.002, BASE_LNG)],
        meals=[_place("한국집"), _place("왱이집")],
        cafes=[_place("툇마루")],
        food_images={"한국집": "http://kto/food.jpg"},
    )
    days = await assemble_days(PlanIntent(region="강릉", days=1), cand)
    slots = days[0].slots
    assert [s.label for s in slots] == ["오전", "점심", "오후", "카페", "저녁"]
    assert [s.source for s in slots] == ["kto", "naver", "kto", "naver", "naver"]
    lunch = slots[1]
    assert lunch.imageUrl == "http://kto/food.jpg"
    assert lunch.links.naver and "map.naver.com" in lunch.links.naver
    assert lunch.links.kakao and "map.kakao.com" in lunch.links.kakao


async def test_walk_leg_for_short_distance_and_transit_fallback():
    cand = _cand(
        [_spot("a1", BASE_LAT, BASE_LNG), _spot("a2", BASE_LAT + 0.05, BASE_LNG)],
        meals=[_place("한국집", BASE_LAT + 0.001, BASE_LNG)],
    )
    days = await assemble_days(PlanIntent(region="강릉", days=1), cand)
    slots = days[0].slots
    walk = slots[1].travelFromPrev
    assert walk is not None and walk.mode == "walk" and walk.minutes >= 2
    transit = slots[2].travelFromPrev
    assert transit is not None and transit.mode == "transit" and transit.minutes > 0


async def test_multi_day_chunks_attractions():
    spots = [_spot(f"a{i}", BASE_LAT + 0.001 * i, BASE_LNG) for i in range(1, 5)]
    days = await assemble_days(PlanIntent(region="강릉", days=2), _cand(spots))
    assert [d.index for d in days] == [1, 2]
    all_names = [s.name for d in days for s in d.slots]
    assert len(all_names) == len(set(all_names))


async def test_raises_without_attractions():
    with pytest.raises(PlanNotEnoughSpots):
        await assemble_days(PlanIntent(region="강릉", days=1), _cand([]))
