from __future__ import annotations

import asyncio

from app.core.db import AsyncSession
from app.core.logging import get_logger
from app.kto.display import t1_display_url
from app.ml.embedding import embedder
from app.modules.plan import repositories
from app.modules.plan.errors import PlanNotEnoughSpots
from app.modules.plan.schemas import PhotoMatchCard, PhotoMatchResponse
from app.modules.plan.services.ingest import ALLOWED_IMAGE_MIMES, MAX_IMAGE_BYTES
from app.web.errors import ImageInvalid

logger = get_logger(__name__)

MATCH_LIMIT = 12


async def match_photo(
    session: AsyncSession, *, image_bytes: bytes, image_mime: str | None
) -> PhotoMatchResponse:
    if not image_bytes or len(image_bytes) > MAX_IMAGE_BYTES:
        raise ImageInvalid()
    if image_mime not in ALLOWED_IMAGE_MIMES:
        raise ImageInvalid()

    try:
        vector = await asyncio.to_thread(embedder.embed_image, image_bytes)
    except Exception as exc:
        logger.warning("plan.photo.embed_failed", error=str(exc))
        raise ImageInvalid() from exc

    rows = await repositories.match_spots_by_vector(session, vector, limit=MATCH_LIMIT)
    if not rows:
        raise PlanNotEnoughSpots()

    matches = [
        PhotoMatchCard(
            contentId=row.content_id,
            title=row.title,
            category=row.category,
            address=row.addr1,
            lat=row.lat,
            lng=row.lng,
            imageUrl=t1_display_url(row.image_url, row.cpyrht_div_cd),
            similarity=round(max(0.0, min(1.0, 1.0 - row.distance)), 3),
        )
        for row in rows
    ]
    logger.info("plan.photo_match.done", matches=len(matches))
    return PhotoMatchResponse(matches=matches)
