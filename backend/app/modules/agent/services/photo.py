from __future__ import annotations

import asyncio

from app.core.db import AsyncSession
from app.core.logging import get_logger
from app.ml.embedding import embedder
from app.modules.agent import repositories
from app.modules.agent.errors import AgentNoResults
from app.modules.agent.repositories import VectorMatchRow
from app.web.errors import ImageInvalid

logger = get_logger(__name__)

MATCH_LIMIT = 12
MAX_IMAGE_BYTES = 8 * 1024 * 1024
ALLOWED_IMAGE_MIMES = {"image/jpeg", "image/png", "image/webp", "image/heic"}


async def match_photo(
    session: AsyncSession, *, image_bytes: bytes, image_mime: str | None
) -> list[VectorMatchRow]:
    if not image_bytes or len(image_bytes) > MAX_IMAGE_BYTES:
        raise ImageInvalid()
    if image_mime not in ALLOWED_IMAGE_MIMES:
        raise ImageInvalid()

    try:
        vector = await asyncio.to_thread(embedder.embed_image, image_bytes)
    except Exception as exc:
        logger.warning("agent.photo.embed_failed", error=str(exc))
        raise ImageInvalid() from exc

    rows = await repositories.match_spots_by_vector(session, vector, limit=MATCH_LIMIT)
    if not rows:
        raise AgentNoResults()

    logger.info("agent.photo_match.done", matches=len(rows))
    return rows


def similarity(row: VectorMatchRow) -> float:
    return round(max(0.0, min(1.0, 1.0 - row.distance)), 3)
