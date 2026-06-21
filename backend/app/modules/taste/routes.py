"""TST routes. Endpoints mirror API spec §6."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, UploadFile, status

from app.core.db import DbSession
from app.core.schemas import ok
from app.modules.spots.schemas import SimilarNeighbor
from app.modules.taste.services import photo_search as photo_search_service

router = APIRouter(tags=["TST · mood analysis"])


@router.post(
    "/taste/photo-search",
    status_code=status.HTTP_200_OK,
    summary="Photo upload → CLIP embedding → similar spots top-N",
)
async def photo_search(
    image: UploadFile,
    session: DbSession,
    limit: int = Query(default=10, ge=1, le=30),
) -> dict[str, Any]:
    """Embed the uploaded image in memory (bytes discarded immediately, never
    persisted — KTO compliance) and return the nearest spots. An empty result
    is a valid 200 (empty list), not an error.
    """
    image_bytes = await image.read()
    neighbors = await photo_search_service(session, image_bytes, limit=limit)
    return ok(
        [
            SimilarNeighbor(
                contentId=row.content_id,
                title=row.title,
                firstImageUrl=row.first_image_url,
                addr1=row.addr1,
                mapx=row.mapx,
                mapy=row.mapy,
                distance=distance,
            )
            for row, distance in neighbors
        ]
    )
