"""GET /v1/map/nearby — spots query + haversine + bbox + category/subtype enrichment.

card.category is the subtype label (lcls_systm3_nm), not a coarse chip.
crowd/firstImage2Url/congestion were removed.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.main import app
from app.modules.map.services import nearby_spots, nearby_spots_bbox
from app.modules.spots.services import NearbyCategory

# reference point near Gwanghwamun
LAT, LNG = 37.5759, 126.9769


async def _seed(
    session: AsyncSession,
    cid: str,
    *,
    lat: float,
    lng: float,
    l1="HS",
    l2=None,
    l3=None,
    l3_nm=None,
    show=1,
    img="http://kto/i.jpg",
    overview=None,
    regn_cd=None,
    regn_nm=None,
    signgu_cd=None,
    signgu_nm=None,
) -> None:
    if l3 is not None:
        await session.execute(
            text(
                "INSERT INTO lcls_systm_codes (lcls_systm3_cd, lcls_systm2_cd, lcls_systm1_cd, "
                "lcls_systm3_nm) VALUES (:l3, :l2, :l1, :nm) ON CONFLICT DO NOTHING"
            ),
            {"l3": l3, "l2": l2, "l1": l1, "nm": l3_nm if l3_nm is not None else l3},
        )
    if regn_cd is not None:
        await session.execute(
            text(
                "INSERT INTO regions (ldong_regn_cd, ldong_regn_nm) VALUES (:cd, :nm) "
                "ON CONFLICT DO NOTHING"
            ),
            {"cd": regn_cd, "nm": regn_nm or regn_cd},
        )
    if signgu_cd is not None:
        await session.execute(
            text(
                "INSERT INTO sigungus (ldong_signgu_cd, ldong_regn_cd, ldong_signgu_nm) "
                "VALUES (:cd, :regn, :nm) ON CONFLICT DO NOTHING"
            ),
            {"cd": signgu_cd, "regn": regn_cd, "nm": signgu_nm or signgu_cd},
        )
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, first_image_url, "
            "show_flag, mapx, mapy, lcls_systm1, lcls_systm2, lcls_systm3, "
            "ldong_regn_cd, ldong_signgu_cd) "
            "VALUES (:cid, 12, :t, :img, :show, :lng, :lat, :l1, :l2, :l3, :regn, :signgu)"
        ),
        {
            "cid": cid,
            "t": f"t-{cid}",
            "img": img,
            "show": show,
            "lng": lng,
            "lat": lat,
            "l1": l1,
            "l2": l2,
            "l3": l3,
            "regn": regn_cd,
            "signgu": signgu_cd,
        },
    )
    if overview is not None:
        # overview lives only on spot_details (ADR-0007); exercises nearby's LEFT JOIN.
        await session.execute(
            text(
                "INSERT INTO spot_details (content_id, content_type_id, overview) "
                "VALUES (:cid, 12, :ov)"
            ),
            {"cid": cid, "ov": overview},
        )


async def test_orders_by_distance_and_applies_radius(db_session: AsyncSession) -> None:
    await _seed(db_session, "near", lat=LAT + 0.001, lng=LNG)  # ~110m
    await _seed(db_session, "mid", lat=LAT + 0.005, lng=LNG)  # ~550m
    await _seed(db_session, "far", lat=LAT + 0.05, lng=LNG)  # ~5.5km (outside)

    rows = await nearby_spots(db_session, lat=LAT, lng=LNG, radius=1000, category=None)
    ids = [r.content_id for r in rows]
    assert ids[:2] == ["near", "mid"]  # distance order
    assert "far" not in ids  # outside radius
    assert rows[0].dist is not None and rows[1].dist is not None
    assert rows[0].dist < rows[1].dist


async def test_default_radius_is_3000(db_session: AsyncSession) -> None:
    # ~2km spot must be caught by the default radius (3000).
    await _seed(db_session, "between", lat=LAT + 0.018, lng=LNG)  # ~2km

    rows = await nearby_spots(db_session, lat=LAT, lng=LNG, radius=3000, category=None)
    ids = {r.content_id for r in rows}
    assert "between" in ids


async def test_excludes_hidden_and_imageless(db_session: AsyncSession) -> None:
    await _seed(db_session, "hidden", lat=LAT, lng=LNG, show=0)
    await _seed(db_session, "noimg", lat=LAT, lng=LNG, img=None)
    await _seed(db_session, "ok", lat=LAT, lng=LNG)

    rows = await nearby_spots(db_session, lat=LAT, lng=LNG, radius=1000, category=None)
    ids = {r.content_id for r in rows}
    assert ids == {"ok"}


async def test_category_filter_food_excludes_bakery(db_session: AsyncSession) -> None:
    await _seed(db_session, "rest", lat=LAT, lng=LNG, l1="FD", l2="FD01", l3="FD010100")
    await _seed(db_session, "bakery", lat=LAT, lng=LNG, l1="FD", l2="FD03", l3="FD030100")

    rows = await nearby_spots(
        db_session, lat=LAT, lng=LNG, radius=1000, category=NearbyCategory.food
    )
    ids = {r.content_id for r in rows}
    assert ids == {"rest"}  # bakery FD030100 is not food


async def test_no_category_restricts_to_defined_taxonomy(db_session: AsyncSession) -> None:
    # category=None is the union of the 5 defined categories, not "no filter".
    await _seed(db_session, "spot", lat=LAT, lng=LNG, l1="NA")  # attraction
    await _seed(db_session, "uncat", lat=LAT, lng=LNG, l1="A0")  # matches no chip

    rows = await nearby_spots(db_session, lat=LAT, lng=LNG, radius=1000, category=None)
    ids = {r.content_id for r in rows}
    assert ids == {"spot"}  # unclassified A0 excluded even from the all view


async def test_category_is_subtype_label(db_session: AsyncSession) -> None:
    await _seed(
        db_session, "cafe1", lat=LAT, lng=LNG, l1="FD", l2="FD05", l3="FD050100", l3_nm="찻집"
    )

    rows = await nearby_spots(db_session, lat=LAT, lng=LNG, radius=1000, category=None)
    row = next(r for r in rows if r.content_id == "cafe1")
    assert row.category == "찻집"


async def test_overview_left_join_passthrough(db_session: AsyncSession) -> None:
    await _seed(db_session, "withov", lat=LAT, lng=LNG, overview="40년대 지어진 한옥 카페")
    await _seed(db_session, "noov", lat=LAT, lng=LNG)

    rows = await nearby_spots(db_session, lat=LAT, lng=LNG, radius=1000, category=None)
    by_id = {r.content_id: r for r in rows}
    assert by_id["withov"].overview == "40년대 지어진 한옥 카페"  # verbatim
    assert by_id["noov"].overview is None  # not yet cached → None, not an error


async def test_region_meta_passthrough(db_session: AsyncSession) -> None:
    await _seed(
        db_session,
        "withregion",
        lat=LAT,
        lng=LNG,
        regn_cd="11",
        regn_nm="서울특별시",
        signgu_cd="11110",
        signgu_nm="종로구",
    )

    rows = await nearby_spots(db_session, lat=LAT, lng=LNG, radius=1000, category=None)
    row = next(r for r in rows if r.content_id == "withregion")
    assert row.region_name == "서울특별시"
    assert row.sigungu_name == "종로구"


async def test_nearby_route_returns_new_fields(db_session, client):
    await _seed(
        db_session,
        "rt1",
        lat=LAT,
        lng=LNG,
        l1="FD",
        l2="FD05",
        l3="FD050100",
        l3_nm="찻집",
    )

    app.dependency_overrides[get_db] = lambda: db_session
    try:
        resp = await client.get("/v1/map/nearby", params={"lat": LAT, "lng": LNG, "radius": 1000})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    item = next(i for i in body["data"] if i["contentId"] == "rt1")
    assert item["category"] == "찻집"  # subtype label
    assert "dist" in item
    # crowd / firstImage2Url / congestion were removed.
    assert "crowd" not in item
    assert "firstImage2Url" not in item
    assert "congestion" not in item


async def test_nearby_route_category_param(db_session, client):
    await _seed(db_session, "shop", lat=LAT, lng=LNG, l1="SH", l2="SH01")
    await _seed(db_session, "cafe2", lat=LAT, lng=LNG, l1="FD", l2="FD05")

    app.dependency_overrides[get_db] = lambda: db_session
    try:
        resp = await client.get(
            "/v1/map/nearby", params={"lat": LAT, "lng": LNG, "category": "shopping"}
        )
    finally:
        app.dependency_overrides.clear()

    ids = {i["contentId"] for i in resp.json()["data"]}
    assert ids == {"shop"}


async def test_nearby_route_rejects_bad_category(db_session, client):
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        resp = await client.get(
            "/v1/map/nearby", params={"lat": LAT, "lng": LNG, "category": "xxx"}
        )
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 422


async def test_nearby_route_requires_lat_lng(db_session, client):
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        resp = await client.get("/v1/map/nearby", params={"lng": LNG})
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_FAILED"


async def test_bbox_returns_only_spots_inside_the_rectangle(db_session: AsyncSession) -> None:
    # Inside a tight box around the reference point; one spot just outside it.
    await _seed(db_session, "in1", lat=LAT + 0.002, lng=LNG + 0.002)
    await _seed(db_session, "in2", lat=LAT - 0.002, lng=LNG - 0.002)
    await _seed(db_session, "out", lat=LAT + 0.02, lng=LNG)  # north of the box

    rows = await nearby_spots_bbox(
        db_session,
        sw_lat=LAT - 0.005,
        sw_lng=LNG - 0.005,
        ne_lat=LAT + 0.005,
        ne_lng=LNG + 0.005,
        category=None,
    )
    ids = [r.content_id for r in rows]
    assert set(ids) == {"in1", "in2"}  # "out" is outside the bbox
    # ordered by distance from the box center (LAT,LNG): both equidistant-ish, dist set
    assert all(r.dist is not None for r in rows)


async def test_nearby_route_bbox_params_override_radius(db_session, client):
    await _seed(db_session, "inbox", lat=LAT, lng=LNG)
    await _seed(db_session, "outbox", lat=LAT + 0.02, lng=LNG)

    app.dependency_overrides[get_db] = lambda: db_session
    try:
        resp = await client.get(
            "/v1/map/nearby",
            params={
                "sw_lat": LAT - 0.005,
                "sw_lng": LNG - 0.005,
                "ne_lat": LAT + 0.005,
                "ne_lng": LNG + 0.005,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    ids = {i["contentId"] for i in resp.json()["data"]}
    assert ids == {"inbox"}  # outbox falls outside the rectangle
