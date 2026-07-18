from __future__ import annotations

import asyncio
import uuid

from redis.asyncio import Redis

from app.core.db import AsyncSession
from app.core.logging import get_logger
from app.ml.embedding import embedder
from app.modules.plan.labels import category_label
from app.modules.plan.llm import describe_image
from app.modules.plan.repositories import PhotoMatchRow, match_spots_by_vector
from app.modules.plan.schemas import MatchCard, PhotoResponse
from app.modules.plan.services.chat import load_thread_state, save_thread_state
from app.web.errors import ImageInvalid, PlanNotEnoughSpots

logger = get_logger(__name__)

_MATCH_LIMIT = 12
_MAX_IMAGE_BYTES = 8 * 1024 * 1024
_ALLOWED_MIME = ("image/jpeg", "image/png", "image/webp", "image/heic")
_FALLBACK_DESCRIPTION = "분위기 좋은 사진이네요. 닮은 국내 여행지를 찾아볼까요?"


def _to_card(row: PhotoMatchRow) -> MatchCard:
    return MatchCard(
        contentId=row.content_id,
        name=row.title,
        category=category_label(row.category),
        address=row.addr1,
        lat=row.lat,
        lng=row.lng,
        imageUrl=row.image_url,
        similarity=max(0.0, min(1.0, 1.0 - row.distance)),
    )


async def handle_photo(
    session: AsyncSession,
    redis: Redis,
    *,
    thread_id: str | None,
    image_bytes: bytes,
    mime_type: str,
) -> PhotoResponse:
    if not image_bytes or len(image_bytes) > _MAX_IMAGE_BYTES:
        raise ImageInvalid()
    if mime_type not in _ALLOWED_MIME:
        raise ImageInvalid()

    try:
        vector = await asyncio.to_thread(embedder.embed_image, image_bytes)
    except Exception as exc:
        logger.warning("plan.photo.embed_failed", error=str(exc))
        raise ImageInvalid() from exc

    matches_task = asyncio.create_task(match_spots_by_vector(session, vector, limit=_MATCH_LIMIT))
    description = await describe_image(image_bytes, mime_type) or _FALLBACK_DESCRIPTION
    rows = await matches_task
    if not rows:
        raise PlanNotEnoughSpots()

    cards = [_to_card(r) for r in rows]

    tid = thread_id or uuid.uuid4().hex
    state = await load_thread_state(redis, tid)
    messages = state.get("messages") or []
    messages.append({"role": "user", "text": "(사진을 올렸다)"})
    messages.append({"role": "model", "text": description})
    state["messages"] = messages
    state["matches"] = [
        {
            "contentId": c.contentId,
            "name": c.name,
            "lat": c.lat,
            "lng": c.lng,
            "address": c.address,
            "imageUrl": c.imageUrl,
            "category": c.category,
            "similarity": c.similarity,
        }
        for c in cards
    ]
    await save_thread_state(redis, tid, state)

    logger.info("plan.photo.matched", matches=len(cards))
    return PhotoResponse(threadId=tid, description=description, matches=cards)
