from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agent.services import retrieve
from app.modules.spots.services import NearbyCategory, find_nearby_spots

REGION = "전북특별자치도 정읍시"


async def _seed_food_world(session: AsyncSession) -> None:
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, addr1, first_image_url, "
            "show_flag, mapx, mapy, lcls_systm1, lcls_systm2, lcls_systm3) "
            "VALUES (:cid, 39, :title, :addr, 'http://kto/i.jpg', 1, 126.85, 35.57, "
            ":l1, :l2, :l3)"
        ),
        [
            {
                "cid": "dish-food",
                "title": "정읍 삼겹살마을",
                "addr": f"{REGION} 1",
                "l1": "FD",
                "l2": "FD01",
                "l3": None,
            },
            {
                "cid": "generic-food",
                "title": "정읍 고향식당",
                "addr": f"{REGION} 2",
                "l1": "FD",
                "l2": "FD01",
                "l3": None,
            },
            {
                "cid": "second-dish-food",
                "title": "정읍 보쌈마을",
                "addr": f"{REGION} 3",
                "l1": "FD",
                "l2": "FD01",
                "l3": None,
            },
            {
                "cid": "multi-dish-food",
                "title": "정읍 삼겹살보쌈",
                "addr": f"{REGION} 4",
                "l1": "FD",
                "l2": "FD01",
                "l3": None,
            },
            {
                "cid": "dish-attraction",
                "title": "삼겹살문화관",
                "addr": f"{REGION} 5",
                "l1": "NA",
                "l2": "NA01",
                "l3": None,
            },
            {
                "cid": "generic-cafe",
                "title": "정읍 느린커피",
                "addr": f"{REGION} 6",
                "l1": "FD",
                "l2": "FD05",
                "l3": None,
            },
        ],
    )


async def test_region_dish_search_requires_food_category_and_title_evidence(
    db_session: AsyncSession,
) -> None:
    await _seed_food_world(db_session)

    rows = await retrieve.search_food(
        db_session,
        action="food",
        region_prefixes=[REGION],
        title_terms=["삼겹살"],
    )

    assert {row.content_id for row in rows} == {"dish-food", "multi-dish-food"}


async def test_region_dish_search_returns_zero_without_title_evidence(
    db_session: AsyncSession,
) -> None:
    await _seed_food_world(db_session)

    rows = await retrieve.search_food(
        db_session,
        action="food",
        region_prefixes=[REGION],
        title_terms=["국밥"],
    )

    assert rows == []


async def test_region_dish_search_requires_every_requested_title_term(
    db_session: AsyncSession,
) -> None:
    await _seed_food_world(db_session)

    rows = await retrieve.search_food(
        db_session,
        action="food",
        region_prefixes=[REGION],
        title_terms=["삼겹살", "보쌈"],
    )

    assert [row.content_id for row in rows] == ["multi-dish-food"]


async def test_nearby_dish_search_requires_every_requested_title_term(
    db_session: AsyncSession,
) -> None:
    await _seed_food_world(db_session)

    rows = await find_nearby_spots(
        db_session,
        lat=35.57,
        lng=126.85,
        radius=1000,
        category=NearbyCategory.food,
        title_terms=["삼겹살", "보쌈"],
    )

    assert [row.content_id for row in rows] == ["multi-dish-food"]


async def test_generic_food_and_cafe_searches_keep_their_broad_pools(
    db_session: AsyncSession,
) -> None:
    await _seed_food_world(db_session)

    food = await retrieve.search_food(db_session, action="food", region_prefixes=[REGION])
    cafe = await retrieve.search_food(db_session, action="cafe", region_prefixes=[REGION])

    assert {row.content_id for row in food} == {
        "dish-food",
        "generic-food",
        "second-dish-food",
        "multi-dish-food",
    }
    assert {row.content_id for row in cafe} == {"generic-cafe"}
