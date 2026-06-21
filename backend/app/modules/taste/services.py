"""TST service layer (role-split WBS W6).

Photo-search: a user-uploaded photo is CLIP-embedded in memory, the bytes are
discarded immediately (never persisted — KTO compliance), and the embedding is
used to find the nearest active spots via pgvector.
"""

from __future__ import annotations

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.embedding import embedder
from app.modules.images.services import find_neighbors_by_vector
from app.modules.spots.services import SpotCardRow, load_spot_cards_by_ids

_MAX_PHOTO_NEIGHBORS = 50


async def photo_search(
    session: AsyncSession,
    image_bytes: bytes,
    *,
    limit: int = 10,
) -> list[tuple[SpotCardRow, float]]:
    """Embed the uploaded photo in memory, then return the nearest active spots
    ordered by ascending cosine distance.

    The image bytes are consumed only to produce the embedding and are not
    persisted anywhere. Returns an empty list when the embedding has no
    neighbors (a valid 200 empty result, not an error).
    """
    limit = max(1, min(limit, _MAX_PHOTO_NEIGHBORS))

    embedding = await asyncio.to_thread(embedder.embed_image, image_bytes)
    pairs = await find_neighbors_by_vector(session, embedding, limit=limit)
    if not pairs:
        return []

    cards = await load_spot_cards_by_ids(session, [cid for cid, _ in pairs])
    return [(cards[cid], distance) for cid, distance in pairs if cid in cards]
