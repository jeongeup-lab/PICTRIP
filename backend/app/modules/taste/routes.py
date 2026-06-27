"""TST routes. Endpoints mirror API spec §6."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, UploadFile, status

from app.core.db import DbSession
from app.core.schemas import ok
from app.modules.taste.schemas import PhotoMatch, PhotoSearchResponse
from app.modules.taste.services import photo_search as photo_search_service

router = APIRouter(tags=["TST · mood analysis"])


@router.post(
    "/taste/photo-search",
    status_code=status.HTTP_200_OK,
    summary="Photo upload → CLIP embedding → similar spots (calibrated floor)",
)
async def photo_search(
    image: UploadFile,
    session: DbSession,
    lat: float | None = Query(default=None),
    lng: float | None = Query(default=None),
) -> dict[str, Any]:
    image_bytes = await image.read()
    result = await photo_search_service(session, image_bytes, lat=lat, lng=lng)
    payload = PhotoSearchResponse(
        matches=[
            PhotoMatch(
                contentId=m.card.content_id,
                title=m.card.title,
                firstImageUrl=m.card.first_image_url,
                addr1=m.card.addr1,
                mapx=m.card.mapx,
                mapy=m.card.mapy,
                category=m.card.lcls_systm3_nm,
                similarity=m.similarity,
                distance=m.distance,
                regionName=m.region_name,
                sigunguName=m.sigungu_name,
            )
            for m in result.matches
        ],
        queryHadLocation=result.query_had_location,
    )
    return ok(payload)
