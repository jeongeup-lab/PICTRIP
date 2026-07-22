from __future__ import annotations

import itertools

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.kto.client import get_kto
from app.main import app
from app.modules.plan.errors import (
    PlanNoPlacesFound,
    PlanNotFound,
    PlanSourceInvalid,
    PlanTranscriptThin,
)
from app.modules.plan.schemas import AssembleRequest, ExtractedPlace, ResolvedPlace, ResolvedSpot
from app.modules.plan.services import assemble, ingest
from app.modules.plan.services.extract import (
    THIN_TRANSCRIPT_CHARS,
    _no_places_error,
    _validate_places,
)
from app.modules.plan.services.ingest import IngestInput
from app.modules.plan.youtube import extract_video_id
from app.web.errors import ImageInvalid


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://www.youtube.com/watch?v=HnhIcurWJCk", "HnhIcurWJCk"),
        ("https://youtu.be/HnhIcurWJCk", "HnhIcurWJCk"),
        ("https://youtu.be/HnhIcurWJCk?si=abc", "HnhIcurWJCk"),
        ("https://m.youtube.com/watch?v=abc123&t=10s", "abc123"),
        ("https://www.youtube.com/shorts/xyz789", "xyz789"),
        ("youtube.com/watch?v=noscheme1", "noscheme1"),
        ("https://www.youtube.com/watch", None),
        ("https://example.com/watch?v=abc", None),
        ("https://www.instagram.com/p/abc/", None),
    ],
)
def test_extract_video_id(url: str, expected: str | None) -> None:
    assert extract_video_id(url) == expected


async def test_ingest_rejects_empty_input() -> None:
    with pytest.raises(PlanSourceInvalid):
        await ingest.normalize(text=None, url=None, image_bytes=None, image_mime=None)
    with pytest.raises(PlanSourceInvalid):
        await ingest.normalize(text="   ", url=None, image_bytes=None, image_mime=None)


async def test_ingest_rejects_bad_images() -> None:
    with pytest.raises(ImageInvalid):
        await ingest.normalize(
            text=None,
            url=None,
            image_bytes=b"x" * (ingest.MAX_IMAGE_BYTES + 1),
            image_mime="image/jpeg",
        )
    with pytest.raises(ImageInvalid):
        await ingest.normalize(text=None, url=None, image_bytes=b"gif", image_mime="image/gif")


async def test_ingest_text_path() -> None:
    source = await ingest.normalize(
        text="  오동도 다녀왔어요  ", url=None, image_bytes=None, image_mime=None
    )
    assert source.kind == "text"
    assert source.raw_text == "오동도 다녀왔어요"


def test_validate_places_dedupes_and_fills_order() -> None:
    places = _validate_places(
        [
            {"name": "오동도", "placeType": "attraction"},
            {"name": "오동도", "nameKo": "오동도", "placeType": "attraction"},
            {"name": "남진이네", "placeType": "restaurant", "orderHint": 7},
            {"name": "", "placeType": "cafe"},
            {"placeType": "cafe"},
        ]
    )
    assert [p.name for p in places] == ["오동도", "남진이네"]
    assert places[0].orderHint == 1
    assert places[1].orderHint == 7


def test_no_places_error_by_source() -> None:
    thin = IngestInput(kind="youtube", raw_text="[음악] 짧은 자막")
    assert isinstance(_no_places_error(thin), PlanTranscriptThin)

    long_text = "자막 " * THIN_TRANSCRIPT_CHARS
    spoken = _no_places_error(IngestInput(kind="youtube", raw_text=long_text))
    assert isinstance(spoken, PlanNoPlacesFound)
    assert "영상 자막" in spoken.message

    generic = _no_places_error(IngestInput(kind="text", raw_text="장소 없는 글"))
    assert isinstance(generic, PlanNoPlacesFound)
    assert generic.message.startswith("콘텐츠에서")


def _place(
    name: str,
    order: int,
    *,
    place_type: str = "attraction",
    lat: float | None = 34.7,
    lng: float | None = 127.7,
    status: str = "matched",
    address: str = "전라남도 여수시 어딘가",
) -> ResolvedPlace:
    spot = None
    if status in ("matched", "ambiguous"):
        spot = ResolvedSpot(
            contentId=f"c{order}",
            title=name,
            address=address,
            lat=lat,
            lng=lng,
        )
    return ResolvedPlace(
        extracted=ExtractedPlace(name=name, placeType=place_type, orderHint=order),
        spot=spot,
        confidence=1.0 if spot else 0.0,
        status=status,
    )


async def test_assemble_builds_days_and_persists(db_session: AsyncSession) -> None:
    places = [_place(f"장소{i}", i, lat=34.7 + i * 0.01) for i in range(1, 7)]
    places.append(_place("미확인", 7, status="unmatched"))
    response = await assemble.build_schedule(
        db_session,
        AssembleRequest(places=places, days=2, sourceKind="text", sourceTitle="여수"),
    )
    assert response.planId is not None
    assert [day.day for day in response.days] == [1, 2]
    assert [len(day.slots) for day in response.days] == [3, 3]
    first_day = response.days[0]
    assert [slot.timeOfDay for slot in first_day.slots] == ["morning", "afternoon", "evening"]
    assert first_day.slots[0].travelMinutesFromPrev is None
    assert first_day.slots[1].travelMinutesFromPrev >= 1
    assert [p.extracted.name for p in response.unplaced] == ["미확인"]

    loaded = await assemble.load_plan(db_session, response.planId)
    assert loaded.planId == response.planId
    assert len(loaded.days) == 2


async def test_assemble_keeps_regions_together(db_session: AsyncSession) -> None:
    places = []
    for i in range(4):
        places.append(
            _place(
                f"여수{i}",
                1 + i * 2,
                lat=34.76 + i * 0.005,
                lng=127.66,
                address="전라남도 여수시 어딘가",
            )
        )
        places.append(
            _place(
                f"순천{i}",
                2 + i * 2,
                lat=34.95 + i * 0.005,
                lng=127.49,
                address="전라남도 순천시 어딘가",
            )
        )
    response = await assemble.build_schedule(
        db_session, AssembleRequest(places=places, days=2, sourceKind="text")
    )
    day_names = [[slot.place.extracted.name for slot in day.slots] for day in response.days]
    assert all(name.startswith("여수") for name in day_names[0])
    assert all(name.startswith("순천") for name in day_names[1])
    assert response.days[0].regionLabel == "전라남도 여수시"
    assert response.days[1].regionLabel == "전라남도 순천시"


async def test_assemble_routes_day_without_zigzag(db_session: AsyncSession) -> None:
    scrambled_lats = [34.73, 34.71, 34.74, 34.70, 34.72]
    places = [_place(f"장소{i}", i + 1, lat=lat, lng=127.7) for i, lat in enumerate(scrambled_lats)]
    response = await assemble.build_schedule(
        db_session, AssembleRequest(places=places, days=1, sourceKind="text")
    )
    lats = [
        slot.place.spot.lat
        for slot in response.days[0].slots
        if slot.place.spot is not None and slot.place.spot.lat is not None
    ]
    diffs = [b - a for a, b in itertools.pairwise(lats)]
    assert all(d > 0 for d in diffs) or all(d < 0 for d in diffs)


async def test_assemble_day_two_starts_near_day_one_end(db_session: AsyncSession) -> None:
    lats = [34.70, 34.71, 34.72, 34.75, 34.74, 34.73]
    places = [_place(f"장소{i}", i + 1, lat=lat, lng=127.7) for i, lat in enumerate(lats)]
    response = await assemble.build_schedule(
        db_session, AssembleRequest(places=places, days=2, sourceKind="text")
    )
    all_lats = [
        slot.place.spot.lat
        for day in response.days
        for slot in day.slots
        if slot.place.spot is not None and slot.place.spot.lat is not None
    ]
    assert all_lats == sorted(all_lats)


async def test_assemble_places_meals_and_lodging_sensibly(db_session: AsyncSession) -> None:
    places = [
        _place("카페", 1, place_type="cafe"),
        _place("식당", 2, place_type="restaurant"),
        _place("명소", 3, place_type="attraction"),
        _place("숙소", 4, place_type="hotel"),
    ]
    response = await assemble.build_schedule(
        db_session, AssembleRequest(places=places, days=1, sourceKind="text")
    )
    slots = response.days[0].slots
    assert slots[0].place.extracted.placeType == "attraction"
    assert slots[-1].place.extracted.placeType == "hotel"


async def test_assemble_follows_daily_meal_rhythm(db_session: AsyncSession) -> None:
    places = [
        _place("점심", 1, place_type="restaurant", lat=34.702),
        _place("카페", 2, place_type="cafe", lat=34.703),
        _place("저녁", 3, place_type="restaurant", lat=34.705),
        _place("명소A", 4, lat=34.701),
        _place("명소B", 5, lat=34.704),
    ]
    response = await assemble.build_schedule(
        db_session, AssembleRequest(places=places, days=1, sourceKind="photo")
    )
    types = [slot.place.extracted.placeType for slot in response.days[0].slots]
    assert types[0] == "attraction"
    assert types[-1] == "restaurant"
    assert types.index("cafe") > types.index("restaurant")


async def test_assemble_generates_region_title(db_session: AsyncSession) -> None:
    places = [_place(f"장소{i}", i) for i in range(1, 5)]
    response = await assemble.build_schedule(
        db_session,
        AssembleRequest(
            places=places,
            days=2,
            sourceKind="youtube",
            sourceTitle="강릉 카페 맛집 브이로그 (ft.남친)",
            sourceUrl="https://youtu.be/abc",
        ),
    )
    assert response.sourceTitle == "여수 2일 코스"
    assert response.sourceUrl == "https://youtu.be/abc"

    loaded = await assemble.load_plan(db_session, response.planId or "")
    assert loaded.sourceTitle == "여수 2일 코스"
    assert loaded.sourceUrl == "https://youtu.be/abc"


async def test_assemble_infers_days_from_place_count(db_session: AsyncSession) -> None:
    places = [_place(f"장소{i}", i) for i in range(1, 9)]
    response = await assemble.build_schedule(
        db_session, AssembleRequest(places=places, sourceKind="text")
    )
    assert len(response.days) == 2
    assert response.planId is not None


async def test_assemble_single_day_without_asking(db_session: AsyncSession) -> None:
    places = [_place(f"장소{i}", i) for i in range(1, 4)]
    response = await assemble.build_schedule(
        db_session, AssembleRequest(places=places, sourceKind="text")
    )
    assert len(response.days) == 1


async def test_assemble_requires_placeable_spot(db_session: AsyncSession) -> None:
    with pytest.raises(PlanNoPlacesFound):
        await assemble.build_schedule(
            db_session,
            AssembleRequest(places=[_place("미확인", 1, status="unmatched")], sourceKind="text"),
        )


async def test_load_plan_missing_raises(db_session: AsyncSession) -> None:
    with pytest.raises(PlanNotFound):
        await assemble.load_plan(db_session, "no-such-plan")


async def test_import_rejects_invalid_body(client: AsyncClient, db_session: AsyncSession) -> None:
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_kto] = lambda: None
    try:
        resp = await client.post("/v1/plan/import", json={})
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "PLAN_SOURCE_INVALID"


async def test_get_plan_not_found(client: AsyncClient, db_session: AsyncSession) -> None:
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        resp = await client.get("/v1/plan/999999999")
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "PLAN_NOT_FOUND"
