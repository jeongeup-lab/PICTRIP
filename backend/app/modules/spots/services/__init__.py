"""SPT service layer — public API aggregator.

Behavior lives in the focused submodules (rows, cards, detail, nearby, saved).
This package re-exports the stable public surface so external callers keep
importing from ``app.modules.spots.services``.
"""

from __future__ import annotations

from app.modules.spots.services import curations, feed
from app.modules.spots.services.cards import (
    bucket_congestion,
    load_active_spot_cards_by_ids,
    load_congestion,
    load_region_meta,
    load_spot_cards_by_ids,
)
from app.modules.spots.services.detail import load_spot_detail
from app.modules.spots.services.nearby import (
    NearbyCategory,
    NearbySpotRow,
    category_predicate,
    derive_category,
    find_nearby_spots,
)
from app.modules.spots.services.rows import (
    MoodTagRow,
    SpotCardRow,
    SpotDetailRow,
    SpotImageRow,
)
from app.modules.spots.services.saved import list_saved_spots, save_spot, unsave_spot

__all__ = [
    "MoodTagRow",
    "NearbyCategory",
    "NearbySpotRow",
    "SpotCardRow",
    "SpotDetailRow",
    "SpotImageRow",
    "bucket_congestion",
    "category_predicate",
    "curations",
    "derive_category",
    "feed",
    "find_nearby_spots",
    "list_saved_spots",
    "load_active_spot_cards_by_ids",
    "load_congestion",
    "load_region_meta",
    "load_spot_cards_by_ids",
    "load_spot_detail",
    "save_spot",
    "unsave_spot",
]
