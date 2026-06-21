"""SPT service layer — public API aggregator.

Behavior lives in the focused submodules (rows, fields, cards, detail, catalog,
similar, related, saved). This package re-exports the stable public surface so
external callers keep importing from ``app.modules.spots.services``.
"""

from __future__ import annotations

from app.modules.spots.services.cards import (
    load_active_spot_cards_by_ids,
    load_spot_cards_by_ids,
)
from app.modules.spots.services.catalog import (
    count_spots_per_mood,
    list_moods,
    list_regions,
    list_spots_by_mood,
    list_spots_by_region,
    pick_active_spot_by_seed,
    search_spots,
)
from app.modules.spots.services.detail import load_spot_detail
from app.modules.spots.services.nearby import (
    NearbyCategory,
    NearbySpotRow,
    category_predicate,
    derive_category,
    find_nearby_spots,
)
from app.modules.spots.services.related import list_related_spots
from app.modules.spots.services.rows import (
    MoodTagRow,
    RelatedSpotRow,
    SimilarResultRow,
    SpotCardRow,
    SpotDetailRow,
    SpotImageRow,
    TrendingSpotRow,
)
from app.modules.spots.services.saved import list_saved_spots, save_spot, unsave_spot
from app.modules.spots.services.similar import find_similar_spots
from app.modules.spots.services.trending import list_trending

__all__ = [
    "MoodTagRow",
    "NearbyCategory",
    "NearbySpotRow",
    "RelatedSpotRow",
    "SimilarResultRow",
    "SpotCardRow",
    "SpotDetailRow",
    "SpotImageRow",
    "TrendingSpotRow",
    "category_predicate",
    "count_spots_per_mood",
    "derive_category",
    "find_nearby_spots",
    "find_similar_spots",
    "list_moods",
    "list_regions",
    "list_related_spots",
    "list_saved_spots",
    "list_spots_by_mood",
    "list_spots_by_region",
    "list_trending",
    "load_active_spot_cards_by_ids",
    "load_spot_cards_by_ids",
    "load_spot_detail",
    "pick_active_spot_by_seed",
    "save_spot",
    "search_spots",
    "unsave_spot",
]
