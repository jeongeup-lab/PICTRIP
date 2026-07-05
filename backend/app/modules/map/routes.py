"""MAP routes. Endpoints mirror API spec §11."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, status

from app.core.db import DbSession
from app.core.redis import RedisDep
from app.core.schemas import ok
from app.modules.map.schemas import RegionLabel, RegionNode
from app.modules.map.services import (
    nearby_cards,
    regions_tree,
    reverse_geocode,
)
from app.modules.spots.services import NearbyCategory

router = APIRouter(tags=["MAP · map"])


@router.get(
    "/map/nearby",
    status_code=status.HTTP_200_OK,
    summary="Location-based recommendation (spots DB: bbox+haversine + category)",
)
async def nearby(
    session: DbSession,
    lat: float | None = Query(default=None, ge=-90, le=90),
    lng: float | None = Query(default=None, ge=-180, le=180),
    radius: int = Query(default=3000, ge=1, le=20000),
    category: NearbyCategory | None = Query(default=None),
    # Visible-map bounding box (south-west + north-east corners). When all four
    # are supplied the query returns spots inside the rectangle the user sees,
    # overriding lat/lng/radius. Otherwise it falls back to center+radius.
    sw_lat: float | None = Query(default=None, ge=-90, le=90),
    sw_lng: float | None = Query(default=None, ge=-180, le=180),
    ne_lat: float | None = Query(default=None, ge=-90, le=90),
    ne_lng: float | None = Query(default=None, ge=-180, le=180),
) -> dict[str, Any]:
    cards = await nearby_cards(
        session,
        lat=lat,
        lng=lng,
        radius=radius,
        category=category,
        sw_lat=sw_lat,
        sw_lng=sw_lng,
        ne_lat=ne_lat,
        ne_lng=ne_lng,
    )
    return ok(cards)


@router.get("/map/region", summary="현위치 행정구역 라벨 (Kakao coord2regioncode)")
async def region(
    redis: RedisDep,
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
) -> dict[str, Any]:
    label: RegionLabel | None = await reverse_geocode(redis, lat=lat, lng=lng)
    return ok(label)


@router.get(
    "/map/regions-tree",
    summary="17 시도 + 시군구 트리 (런타임 AVG centroid, 24h 캐시)",
)
async def regions_tree_route(session: DbSession, redis: RedisDep) -> dict[str, Any]:
    tree = await regions_tree(session, redis)
    return ok([RegionNode.model_validate(node) for node in tree])
