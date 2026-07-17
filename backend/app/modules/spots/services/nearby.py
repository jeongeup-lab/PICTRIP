"""Nearby SPT service — bbox+haversine distance query + category taxonomy.
SPT owns Spot queries; MAP only merges crowd (Redis) onto the returned rows."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.modules.spots.models import LclsSystmCode, Spot, SpotDetail

_MAX_NUM_OF_ROWS = 50
_EARTH_RADIUS_M = 6_371_000.0
_VE_EXCLUDE = ("VE06", "VE07", "VE08", "VE09", "VE10", "VE11")


class NearbyCategory(StrEnum):
    attraction = "attraction"
    food = "food"
    cafe = "cafe"
    leisure = "leisure"
    shopping = "shopping"


@dataclass
class NearbySpotRow:
    content_id: str
    title: str
    first_image_url: str | None
    addr1: str | None
    mapx: float | None
    mapy: float | None
    dist: float | None
    category: str | None = None
    category_group: str | None = None
    overview: str | None = None
    region_name: str | None = None
    sigungu_name: str | None = None


def category_predicate(cat: NearbyCategory) -> ColumnElement[bool]:
    """Category SSOT rule -> SQLAlchemy boolean for the nearby WHERE."""
    if cat is NearbyCategory.attraction:
        return or_(
            Spot.lcls_systm1.in_(("HS", "NA", "EX")),
            and_(
                Spot.lcls_systm1 == "VE",
                or_(Spot.lcls_systm2.is_(None), Spot.lcls_systm2.notin_(_VE_EXCLUDE)),
            ),
        )
    if cat is NearbyCategory.food:
        return and_(
            Spot.lcls_systm2.in_(("FD01", "FD02", "FD03")),
            or_(Spot.lcls_systm3.is_(None), Spot.lcls_systm3 != "FD030100"),
        )
    if cat is NearbyCategory.cafe:
        return or_(Spot.lcls_systm2 == "FD05", Spot.lcls_systm3 == "FD030100")
    if cat is NearbyCategory.leisure:
        return Spot.lcls_systm1 == "LS"
    return and_(
        Spot.lcls_systm1 == "SH",
        or_(Spot.lcls_systm2.is_(None), Spot.lcls_systm2 != "SH04"),
    )


def all_categories_predicate() -> ColumnElement[bool]:
    """Union of the 5 defined categories — uncategorized spots (숙박/축제/공연 등)
    excluded. The taxonomy SSOT for every "tourist-worthy spots only" gate."""
    return or_(*(category_predicate(c) for c in NearbyCategory))


def _predicate_sql(predicate: ColumnElement[bool]) -> str:
    return str(
        predicate.compile(
            dialect=postgresql.dialect(),  # type: ignore[no-untyped-call]
            compile_kwargs={"literal_binds": True},
        )
    )


def all_categories_sql() -> str:
    """all_categories_predicate rendered as raw SQL for text() queries that join
    the ``spots`` table by its real name (no alias). Generated from the ORM
    predicate so the category taxonomy stays single-source."""
    return _predicate_sql(all_categories_predicate())


def attraction_category_sql() -> str:
    """category_predicate(attraction) rendered as raw SQL — the overseas→domestic
    matching gate: 명소 매칭에는 attraction 버킷만 후보로 허용."""
    return _predicate_sql(category_predicate(NearbyCategory.attraction))


def derive_category(l1: str | None, l2: str | None, l3: str | None) -> str | None:
    """lcls values -> chip code. Order cafe before food: FD030100 is excluded from
    food but included in cafe."""
    if l2 == "FD05" or l3 == "FD030100":
        return "cafe"
    if l2 in ("FD01", "FD02", "FD03") and l3 != "FD030100":
        return "food"
    if l1 in ("HS", "NA", "EX") or (l1 == "VE" and l2 not in _VE_EXCLUDE):
        return "attraction"
    if l1 == "LS":
        return "leisure"
    if l1 == "SH" and l2 != "SH04":
        return "shopping"
    return None


def _dist_expr(lat: float, lng: float) -> ColumnElement[float]:
    """Haversine distance (m) from (lat,lng) to each spot; mapy=lat, mapx=lng.
    acos domain clamped to avoid NaN at the poles."""
    cos_term = func.cos(func.radians(lat)) * func.cos(func.radians(Spot.mapy)) * func.cos(
        func.radians(Spot.mapx) - func.radians(lng)
    ) + func.sin(func.radians(lat)) * func.sin(func.radians(Spot.mapy))
    return (_EARTH_RADIUS_M * func.acos(func.least(1.0, func.greatest(-1.0, cos_term)))).label(
        "dist"
    )


def _base_select(dist: ColumnElement[float], category: NearbyCategory | None):  # type: ignore[no-untyped-def]
    """Shared SELECT + base/category filters for the nearby queries (sans bbox).
    Base: show_flag=1 AND first_image_url IS NOT NULL. category=None means the
    union of the 5 defined categories, NOT no filter — uncategorized spots are excluded."""
    inner = (
        select(
            Spot.content_id.label("content_id"),
            Spot.title.label("title"),
            Spot.first_image_url.label("first_image_url"),
            Spot.addr1.label("addr1"),
            Spot.mapx.label("mapx"),
            Spot.mapy.label("mapy"),
            LclsSystmCode.lcls_systm3_nm.label("category"),
            Spot.lcls_systm1.label("lcls_systm1"),
            Spot.lcls_systm2.label("lcls_systm2"),
            Spot.lcls_systm3.label("lcls_systm3"),
            SpotDetail.overview.label("overview"),
            dist,
        )
        .outerjoin(SpotDetail, SpotDetail.content_id == Spot.content_id)
        .outerjoin(LclsSystmCode, LclsSystmCode.lcls_systm3_cd == Spot.lcls_systm3)
        .where(
            Spot.show_flag == 1,
            Spot.first_image_url.isnot(None),
            Spot.mapx.isnot(None),
            Spot.mapy.isnot(None),
        )
    )
    if category is not None:
        return inner.where(category_predicate(category))
    return inner.where(all_categories_predicate())


def _materialize(result: object) -> list[NearbySpotRow]:
    rows: list[NearbySpotRow] = []
    for r in result:  # type: ignore[attr-defined]
        rows.append(
            NearbySpotRow(
                content_id=r.content_id,
                title=r.title or "",
                first_image_url=r.first_image_url,
                addr1=r.addr1,
                mapx=float(r.mapx) if r.mapx is not None else None,
                mapy=float(r.mapy) if r.mapy is not None else None,
                dist=float(r.dist) if r.dist is not None else None,
                category=r.category,
                category_group=derive_category(r.lcls_systm1, r.lcls_systm2, r.lcls_systm3),
                overview=r.overview,
            )
        )
    return rows


async def find_nearby_spots(
    session: AsyncSession,
    *,
    lat: float,
    lng: float,
    radius: int,
    category: NearbyCategory | None,
) -> list[NearbySpotRow]:
    """Active+image spots within radius m, distance-ordered (crowd merged by MAP)."""
    dlat = radius / 111_320.0
    dlng = radius / (111_320.0 * max(math.cos(math.radians(lat)), 0.01))

    inner = _base_select(_dist_expr(lat, lng), category).where(
        Spot.mapy.between(lat - dlat, lat + dlat),
        Spot.mapx.between(lng - dlng, lng + dlng),
    )
    sub = inner.subquery()
    stmt = select(sub).where(sub.c.dist <= radius).order_by(sub.c.dist).limit(_MAX_NUM_OF_ROWS)
    return _materialize(await session.execute(stmt))


async def find_nearby_spots_bbox(
    session: AsyncSession,
    *,
    sw_lat: float,
    sw_lng: float,
    ne_lat: float,
    ne_lng: float,
    category: NearbyCategory | None,
) -> list[NearbySpotRow]:
    """Active+image spots inside the visible map rectangle (sw..ne), ordered by
    distance from the box center. Same base/category rules as find_nearby_spots;
    the map's bbox replaces the center+radius circle so results match what the
    user sees on screen."""
    min_lat, max_lat = min(sw_lat, ne_lat), max(sw_lat, ne_lat)
    min_lng, max_lng = min(sw_lng, ne_lng), max(sw_lng, ne_lng)
    center_lat = (min_lat + max_lat) / 2
    center_lng = (min_lng + max_lng) / 2

    inner = _base_select(_dist_expr(center_lat, center_lng), category).where(
        Spot.mapy.between(min_lat, max_lat),
        Spot.mapx.between(min_lng, max_lng),
    )
    sub = inner.subquery()
    stmt = select(sub).order_by(sub.c.dist).limit(_MAX_NUM_OF_ROWS)
    return _materialize(await session.execute(stmt))
