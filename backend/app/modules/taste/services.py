"""TST service layer — photo-search (CLIP embed in memory, HNSW-direct over spot_embeddings, S07 §10)."""

from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.embedding import embedder
from app.modules.images.services import find_neighbor_ids_by_vector_direct
from app.modules.spots.services import (
    SpotCardRow,
    load_congestion,
    load_region_meta,
    load_spot_cards_by_ids,
)

_EARTH_RADIUS_M = 6_371_000.0


@dataclass
class PhotoMatchRow:
    card: SpotCardRow
    similarity: float
    distance: float | None  # metres from the query point; None when no lat/lng
    region_name: str | None
    sigungu_name: str | None


@dataclass
class PhotoSearchResult:
    matches: list[PhotoMatchRow]
    query_had_location: bool


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    rlat1, rlat2 = math.radians(lat1), math.radians(lat2)
    dlat = rlat2 - rlat1
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlng / 2) ** 2
    return _EARTH_RADIUS_M * 2 * math.asin(min(1.0, math.sqrt(a)))


async def photo_search(
    session: AsyncSession,
    image_bytes: bytes,
    *,
    lat: float | None = None,
    lng: float | None = None,
) -> PhotoSearchResult:
    # Image bytes embedded in memory only, never persisted (KTO compliance).
    query_had_location = lat is not None and lng is not None

    cap = max(1, settings.PHOTO_SEARCH_MAX)
    embedding = await asyncio.to_thread(embedder.embed_image, image_bytes)
    pairs = await find_neighbor_ids_by_vector_direct(session, embedding, limit=cap)
    if not pairs:
        return PhotoSearchResult(matches=[], query_had_location=query_had_location)

    content_ids = [cid for cid, _ in pairs]
    cards = await load_spot_cards_by_ids(session, content_ids)
    congestion = await load_congestion(session, content_ids)
    region_meta = await load_region_meta(session, content_ids)

    # Keep only spots that hydrated to a card; HNSW-direct query skips show_flag.
    scored: list[PhotoMatchRow] = []
    for cid, distance in pairs:
        card = cards.get(cid)
        if card is None:
            continue
        card.congestion = congestion.get(cid)
        region_name, sigungu_name = region_meta.get(cid, (None, None))
        similarity = max(0.0, min(1.0, 1.0 - distance))
        geo_distance: float | None = None
        if query_had_location and card.mapx is not None and card.mapy is not None:
            assert lat is not None and lng is not None  # narrowed by query_had_location
            geo_distance = _haversine_m(lat, lng, card.mapy, card.mapx)
        scored.append(
            PhotoMatchRow(
                card=card,
                similarity=similarity,
                distance=geo_distance,
                region_name=region_name,
                sigungu_name=sigungu_name,
            )
        )

    scored.sort(key=lambda m: m.similarity, reverse=True)

    floor = settings.PHOTO_SEARCH_SIMILARITY_FLOOR
    above = [m for m in scored if m.similarity >= floor]
    # Top-N soft floor: if nothing clears the calibrated floor, surface the best
    # candidates anyway so a sparse pool isn't silently empty.
    matches = (above or scored)[:cap]
    return PhotoSearchResult(matches=matches, query_had_location=query_had_location)
