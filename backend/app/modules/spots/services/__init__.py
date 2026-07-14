"""SPT service layer — re-exports the public surface from the submodules."""

from __future__ import annotations

from app.modules.spots.services import curations, feed
from app.modules.spots.services.cards import (
    image_bearing_spots_stmt,
    load_active_spot_cards_by_ids,
    load_overview_map,
    load_region_meta,
    load_spot_cards_by_ids,
    lock_current_spot_image,
)
from app.modules.spots.services.concentration import (
    ConcentrationCardRow,
    load_hidden_spots,
    load_hot_spots,
)
from app.modules.spots.services.detail import load_spot_detail
from app.modules.spots.services.nearby import (
    NearbyCategory,
    NearbySpotRow,
    all_categories_predicate,
    all_categories_sql,
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
    "ConcentrationCardRow",
    "NearbyCategory",
    "NearbySpotRow",
    "SpotCardRow",
    "SpotDetailRow",
    "SpotImageRow",
    "all_categories_predicate",
    "all_categories_sql",
    "category_predicate",
    "curations",
    "derive_category",
    "feed",
    "find_nearby_spots",
    "find_nearby_spots_bbox",
    "image_bearing_spots_stmt",
    "list_saved_spots",
    "load_active_spot_cards_by_ids",
    "load_hidden_spots",
    "load_hot_spots",
    "load_overview_map",
    "load_region_meta",
    "load_spot_cards_by_ids",
    "load_spot_detail",
    "lock_current_spot_image",
    "save_spot",
    "unsave_spot",
]
