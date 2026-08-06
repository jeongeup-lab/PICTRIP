from __future__ import annotations

from typing import get_args

from app.modules.agent.schemas import DropAxis, QueryIntent, RefinePatch, Suggestion
from app.modules.agent.services import refine as refine_service

MAX_SUGGESTIONS = 3
ALL_AXES: frozenset[DropAxis] = frozenset(get_args(DropAxis))
WIDEN_REGION_LABEL = "지역 넓히기"


def category_noun(intent: QueryIntent) -> str:
    return intent.categoryKeywords[0] if intent.categoryKeywords else "분위기"


def derive_for_zero(
    intent: QueryIntent,
    *,
    has_coords: bool,
    axes: frozenset[DropAxis] = ALL_AXES,
) -> list[Suggestion]:
    if not _region_releasable(intent, axes, has_coords=has_coords):
        return []
    return [Suggestion(label=WIDEN_REGION_LABEL, patch=RefinePatch(drop="region"))]


def derive(
    intent: QueryIntent,
    *,
    has_coords: bool,
    result_count: int,
    axes: frozenset[DropAxis] = ALL_AXES,
    indoor_available: bool = True,
) -> list[Suggestion]:
    if intent.festivalOnly:
        return []
    chips: list[Suggestion] = []
    if "crowd" in axes:
        if intent.crowdPreference == "any":
            chips.append(
                Suggestion(label="사람 적은 곳만", patch=RefinePatch(crowdPreference="quiet"))
            )
        elif intent.crowdPreference == "quiet":
            chips.append(
                Suggestion(label="유명한 곳으로", patch=RefinePatch(crowdPreference="popular"))
            )
    if "indoor" in axes and not intent.indoorOnly and indoor_available:
        chips.append(Suggestion(label="실내만", patch=RefinePatch(indoorOnly=True)))
    if "near" in axes and has_coords and not intent.nearMe:
        chips.append(Suggestion(label="가까운 순으로", patch=RefinePatch(nearMe=True)))
    return chips[:MAX_SUGGESTIONS]


def _region_releasable(intent: QueryIntent, axes: frozenset[DropAxis], *, has_coords: bool) -> bool:
    return (
        "region" in axes
        and bool(intent.regionHints)
        and not refine_service.drop_leaves_named_place_only(intent, "region", has_coords=has_coords)
    )
