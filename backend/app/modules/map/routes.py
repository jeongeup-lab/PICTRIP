"""MAP routes. Endpoints mirror API spec §11."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, status

from app.core.db import DbSession
from app.core.redis import RedisDep
from app.core.schemas import ok
from app.modules.map.schemas import NearbyCrowd, NearbySpotCard, RegionLabel
from app.modules.map.services import nearby_spots, reverse_geocode
from app.modules.spots.services import NearbyCategory

router = APIRouter(tags=["MAP · map/crowd"])


@router.get(
    "/map/nearby",
    status_code=status.HTTP_200_OK,
    summary="Location-based recommendation (spots DB: bbox+haversine + category + crowd)",
)
async def nearby(
    session: DbSession,
    redis: RedisDep,
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
    radius: int = Query(default=1000, ge=1, le=20000),
    category: NearbyCategory | None = Query(default=None),
) -> dict[str, Any]:
    rows = await nearby_spots(session, redis, lat=lat, lng=lng, radius=radius, category=category)
    return ok(
        [
            NearbySpotCard(
                contentId=r.content_id,
                title=r.title,
                firstImageUrl=r.first_image_url,
                firstImage2Url=r.first_image2_url,
                addr1=r.addr1,
                mapx=r.mapx,
                mapy=r.mapy,
                dist=r.dist,
                category=r.category,
                overview=r.overview,
                crowd=(
                    NearbyCrowd(rate=r.crowd.rate, level=r.crowd.level)
                    if r.crowd is not None
                    else None
                ),
            )
            for r in rows
        ]
    )


@router.get("/map/region", summary="현위치 행정구역 라벨 (Kakao coord2regioncode)")
async def region(
    redis: RedisDep,
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
) -> dict[str, Any]:
    label: RegionLabel | None = await reverse_geocode(redis, lat=lat, lng=lng)
    return ok(label)
