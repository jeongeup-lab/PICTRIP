"""Loader-level tests: home-card loaders derive the map-SSOT `category` chip.

`load_active_spot_cards_by_ids` and `list_spots_by_region` now select the three
`lcls_systm` columns and run `derive_category` over them, so the SpotCardRow they
return carries a chip code (food/cafe/attraction/leisure/shopping/None). The other
card loaders keep `category=None` (backward compat — not exercised here).

Uses the function-scoped `db_session` fixture from conftest.py (outer-tx rollback,
isolated). Seeding is raw `text()` INSERTs over the regions <- sigungus <- spots FK
chain, extended to set lcls_systm{1,2,3} so the category branches are driven.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.main import app
from app.modules.spots.services.cards import load_active_spot_cards_by_ids
from app.modules.spots.services.catalog import list_spots_by_region


async def _ensure_region_refs(
    session: AsyncSession, *, signgu: str | None, regn: str | None
) -> None:
    """Satisfy the spots FK chain regions <- sigungus <- spots."""
    regn_codes = {c for c in (regn, signgu[:2] if signgu else None) if c}
    for code in regn_codes:
        await session.execute(
            text(
                "INSERT INTO regions (ldong_regn_cd, ldong_regn_nm) "
                "VALUES (:c, :c) ON CONFLICT (ldong_regn_cd) DO NOTHING"
            ),
            {"c": code},
        )
    if signgu:
        await session.execute(
            text(
                "INSERT INTO sigungus (ldong_signgu_cd, ldong_regn_cd, ldong_signgu_nm) "
                "VALUES (:s, :r, :s) ON CONFLICT (ldong_signgu_cd) DO NOTHING"
            ),
            {"s": signgu, "r": signgu[:2]},
        )


async def _seed_spot(
    session: AsyncSession,
    *,
    content_id: str,
    title: str,
    signgu: str | None = None,
    regn: str | None = None,
    image: str = "http://kto/first.jpg",
    show_flag: int = 1,
    l1: str | None = None,
    l2: str | None = None,
    l3: str | None = None,
) -> None:
    await _ensure_region_refs(session, signgu=signgu, regn=regn)
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, first_image_url, "
            "addr1, ldong_regn_cd, ldong_signgu_cd, mapx, mapy, show_flag, "
            "lcls_systm1, lcls_systm2, lcls_systm3) "
            "VALUES (:cid, 12, :t, :img, '주소', :r, :s, 127.0, 37.5, :sf, "
            ":l1, :l2, :l3) "
            "ON CONFLICT (content_id) DO NOTHING"
        ),
        {
            "cid": content_id,
            "t": title,
            "img": image,
            "r": regn,
            "s": signgu,
            "sf": show_flag,
            "l1": l1,
            "l2": l2,
            "l3": l3,
        },
    )
    await session.commit()


_VALID_CATEGORIES = {"attraction", "food", "cafe", "leisure", "shopping", None}


@pytest.mark.asyncio
async def test_active_cards_by_ids_derive_category(db_session: AsyncSession) -> None:
    await _seed_spot(db_session, content_id="HC-FOOD", title="식당", l1="FD", l2="FD01")
    await _seed_spot(db_session, content_id="HC-CAFE", title="찻집", l1="FD", l2="FD05")
    await _seed_spot(db_session, content_id="HC-ATTR", title="자연", l1="NA")
    await _seed_spot(db_session, content_id="HC-NONE", title="미분류")

    cards = await load_active_spot_cards_by_ids(
        db_session, ["HC-FOOD", "HC-CAFE", "HC-ATTR", "HC-NONE"]
    )

    assert cards["HC-FOOD"].category == "food"
    assert cards["HC-CAFE"].category == "cafe"
    assert cards["HC-ATTR"].category == "attraction"
    assert cards["HC-NONE"].category is None


@pytest.mark.asyncio
async def test_by_region_derives_category(db_session: AsyncSession) -> None:
    await _seed_spot(
        db_session, content_id="RC-FOOD", title="식당", signgu="51150", l1="FD", l2="FD01"
    )
    await _seed_spot(
        db_session, content_id="RC-CAFE", title="찻집", signgu="51150", l1="FD", l2="FD05"
    )
    await _seed_spot(db_session, content_id="RC-ATTR", title="자연", signgu="51150", l1="NA")
    await _seed_spot(db_session, content_id="RC-NONE", title="미분류", signgu="51150")

    rows = await list_spots_by_region(db_session, signgu_codes=["51150"], regn_codes=[], limit=24)

    by_id = {r.content_id: r for r in rows}
    assert {"RC-FOOD", "RC-CAFE", "RC-ATTR", "RC-NONE"} <= set(by_id)
    # membership-set invariant: every row's category is a valid chip code or None
    assert all(r.category in _VALID_CATEGORIES for r in rows)
    # known seeded spots map to their expected branch
    assert by_id["RC-FOOD"].category == "food"
    assert by_id["RC-CAFE"].category == "cafe"
    assert by_id["RC-ATTR"].category == "attraction"
    assert by_id["RC-NONE"].category is None


# ---------------------------------------------------------------------------
# Route-level tests: the home routes (/v1/spots/by-region, /v1/spots/batch)
# surface `category` on the SpotCard JSON; other SpotCard routes serialize null.
#
# Mirrors the real route-test fixture pattern from test_spots_batch_routes.py /
# test_spots_by_region_routes.py: an outer-tx-rollback fixture that overrides
# get_db. The route tests reuse `_seed_spot` (above) — it already sets the three
# lcls_systm columns, so category branches can be driven through the HTTP layer.
# ---------------------------------------------------------------------------


# NOTE: deliberately NOT autouse (unlike the sibling fixture in
# test_spots_batch_routes.py). This file mixes two fixture regimes: the
# loader-level tests use the conftest `db_session` fixture, while the route
# tests explicitly request `override_db_and_seed`. Making it autouse would force
# every loader test through an unused engine override, so each route test opts
# in by naming the fixture in its signature instead.
@pytest_asyncio.fixture
async def override_db_and_seed() -> AsyncIterator[AsyncSession]:
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
            try:
                yield seed
            finally:
                await seed.close()
                app.dependency_overrides.pop(get_db, None)
        finally:
            if tx.is_active:
                await tx.rollback()
    await eng.dispose()


@pytest.mark.asyncio
async def test_batch_route_exposes_category(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    s = override_db_and_seed
    await _seed_spot(s, content_id="HCR-FOOD", title="식당", signgu="11110", l1="FD", l2="FD01")

    r = await client.get("/v1/spots/batch", params={"ids": "HCR-FOOD"})

    assert r.status_code == 200
    data = r.json()["data"]
    assert data[0]["category"] == "food"


@pytest.mark.asyncio
async def test_by_region_route_exposes_category(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    s = override_db_and_seed
    await _seed_spot(s, content_id="HCR-CAFE", title="찻집", signgu="51150", l1="FD", l2="FD05")
    await _seed_spot(s, content_id="HCR-PLAIN", title="자연", signgu="51150", l1="NA")

    r = await client.get("/v1/spots/by-region", params={"signgu": "51150"})

    assert r.status_code == 200
    items = r.json()["data"]
    assert items, "expected seeded spots in the by-region response"
    # every card carries the category key (backward-compatible additive field)
    assert all("category" in c for c in items)
    by_id = {c["contentId"]: c for c in items}
    assert by_id["HCR-CAFE"]["category"] == "cafe"
    assert by_id["HCR-PLAIN"]["category"] == "attraction"


@pytest.mark.asyncio
async def test_search_route_serializes_category_null(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    """Backward-compat regression: the search route returns SpotCard but does not
    populate category, so it must serialize as null (not absent, not derived)."""
    s = override_db_and_seed
    # search-route seed: no lcls_systm columns needed — the route never derives.
    await s.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, first_image_url, "
            "addr1, mapx, mapy, show_flag) "
            "VALUES ('HCR-SRCH', 12, '제주 바다 산책', 'http://kto/first.jpg', "
            "'주소', 127.0, 37.5, 1) ON CONFLICT (content_id) DO NOTHING"
        )
    )
    await s.commit()

    r = await client.get("/v1/spots/search", params={"q": "바다"})

    assert r.status_code == 200
    data = r.json()["data"]
    assert [c["contentId"] for c in data] == ["HCR-SRCH"]
    assert data[0]["category"] is None
