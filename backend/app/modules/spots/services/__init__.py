"""SPT service layer — re-exports the public surface from the submodules."""

from __future__ import annotations

from app.modules.spots.services import curations, feed
from app.modules.spots.services.cards import (
    load_active_spot_cards_by_ids,
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
    find_nearby_spots_bbox,
)
from app.modules.spots.services.rows import (
    SpotCardRow,
    SpotDetailRow,
    SpotImageRow,
)
from app.modules.spots.services.saved import list_saved_spots, save_spot, unsave_spot

__all__ = [
    "NearbyCategory",
    "NearbySpotRow",
    "SpotCardRow",
    "SpotDetailRow",
    "SpotImageRow",
    "category_predicate",
    "curations",
    "derive_category",
    "feed",
    "find_nearby_spots",
    "find_nearby_spots_bbox",
    "list_saved_spots",
    "load_active_spot_cards_by_ids",
    "load_region_meta",
    "load_spot_cards_by_ids",
    "load_spot_detail",
    "save_spot",
    "unsave_spot",
]
