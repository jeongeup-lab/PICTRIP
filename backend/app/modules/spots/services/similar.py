"""Region-scoped CLIP photo similarity (ADR-0014) — IMG neighbors + SPT join."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ResourceNotFound
from app.modules.images.services import find_neighbor_content_ids
from app.modules.spots.services.cards import _load_spot_card, _load_spot_cards
from app.modules.spots.services.region import _validate_region
from app.modules.spots.services.rows import SimilarResultRow

_MAX_SIMILAR_NEIGHBORS = 50


async def find_similar_spots(
    session: AsyncSession,
    content_id: str,
    *,
    limit: int = 10,
    region: str | None = None,
) -> SimilarResultRow:
    """Look up the query spot, ask IMG for nearest neighbor content_ids,
    and join SPT metadata back in.

    When `region` is a non-empty legal-dong sido code, neighbors are restricted
    to that sido (province) (region-scoped photo match, ADR-0014). No nationwide
    fallback: a sparse region simply yields fewer (or zero) neighbors. Raises
    ValidationFailed if
    the region code is unknown.
    """
    limit = max(1, min(limit, _MAX_SIMILAR_NEIGHBORS))
    query_row = await _load_spot_card(session, content_id)
    if query_row is None:
        raise ResourceNotFound(f"Spot '{content_id}' not found.")

    region_code = await _validate_region(session, region)

    pairs = await find_neighbor_content_ids(session, content_id, limit=limit, region=region_code)
    if not pairs:
        return SimilarResultRow(query=query_row, neighbors=[])

    distance_by_id = dict(pairs)
    rows = await _load_spot_cards(session, list(distance_by_id.keys()))
    rows_by_id = {r.content_id: r for r in rows}
    ordered = [(rows_by_id[cid], distance_by_id[cid]) for cid, _ in pairs if cid in rows_by_id]
    return SimilarResultRow(query=query_row, neighbors=ordered)
