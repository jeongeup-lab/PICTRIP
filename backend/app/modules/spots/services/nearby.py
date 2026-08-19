from __future__ import annotations

import math
from dataclasses import dataclass

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.modules.spots.categories import (
    NearbyCategory,
    all_categories_predicate,
    category_predicate,
    derive_category,
    travel_category_predicate,
)
from app.modules.spots.models import LclsSystmCode, Spot, SpotDetail

_MAX_NUM_OF_ROWS = 50
_EARTH_RADIUS_M = 6_371_000.0


@dataclass
class NearbySpotRow:
    content_id: str
    title: str
    first_image_url: str | None
    addr1: str | None
    mapx: float | None
    mapy: float | None
    dist: float | None
    cpyrht_div_cd: str | None = None
    category: str | None = None
    category_group: str | None = None
    overview: str | None = None
    region_name: str | None = None
    sigungu_name: str | None = None


def _dist_expr(lat: float, lng: float) -> ColumnElement[float]:
    cos_term = func.cos(func.radians(lat)) * func.cos(func.radians(Spot.mapy)) * func.cos(
        func.radians(Spot.mapx) - func.radians(lng)
    ) + func.sin(func.radians(lat)) * func.sin(func.radians(Spot.mapy))
    return (_EARTH_RADIUS_M * func.acos(func.least(1.0, func.greatest(-1.0, cos_term)))).label(
        "dist"
    )


def _base_select(dist: ColumnElement[float], predicate: ColumnElement[bool]):  # type: ignore[no-untyped-def]
    inner = (
        select(
            Spot.content_id.label("content_id"),
            Spot.title.label("title"),
            Spot.first_image_url.label("first_image_url"),
            Spot.cpyrht_div_cd.label("cpyrht_div_cd"),
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
    return inner.where(predicate)


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
                cpyrht_div_cd=r.cpyrht_div_cd,
                category=r.category,
                category_group=derive_category(r.lcls_systm1, r.lcls_systm2, r.lcls_systm3),
                overview=r.overview,
            )
        )
    return rows


def _predicate_for(category: NearbyCategory | None, travel_only: bool) -> ColumnElement[bool]:
    if travel_only:
        return travel_category_predicate()
    if category is not None:
        return category_predicate(category)
    return all_categories_predicate()


async def find_nearby_spots(
    session: AsyncSession,
    *,
    lat: float,
    lng: float,
    radius: int,
    category: NearbyCategory | None,
    travel_only: bool = False,
    title_terms: list[str] | None = None,
) -> list[NearbySpotRow]:
    dlat = radius / 111_320.0
    dlng = radius / (111_320.0 * max(math.cos(math.radians(lat)), 0.01))

    predicate = _predicate_for(category, travel_only)
    if title_terms:
        predicate = and_(
            predicate,
            *(Spot.title.ilike(f"%{term}%") for term in title_terms),
        )
    inner = _base_select(_dist_expr(lat, lng), predicate).where(
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
    min_lat, max_lat = min(sw_lat, ne_lat), max(sw_lat, ne_lat)
    min_lng, max_lng = min(sw_lng, ne_lng), max(sw_lng, ne_lng)
    center_lat = (min_lat + max_lat) / 2
    center_lng = (min_lng + max_lng) / 2

    inner = _base_select(_dist_expr(center_lat, center_lng), _predicate_for(category, False)).where(
        Spot.mapy.between(min_lat, max_lat),
        Spot.mapx.between(min_lng, max_lng),
    )
    sub = inner.subquery()
    stmt = select(sub).order_by(sub.c.dist).limit(_MAX_NUM_OF_ROWS)
    return _materialize(await session.execute(stmt))
