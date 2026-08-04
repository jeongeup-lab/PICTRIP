from __future__ import annotations

from typing import get_args

from app.modules.agent.schemas import DropAxis, QueryIntent, RefinePatch, Suggestion
from app.modules.agent.services import refine as refine_service

MAX_SUGGESTIONS = 3
THIN_RESULT_COUNT = 5
ALL_AXES: frozenset[DropAxis] = frozenset(get_args(DropAxis))
_DROP_ORDER: tuple[DropAxis, ...] = ("crowd", "indoor", "category", "near", "region")
_WIDEN_REGION_LABEL = "지역 넓히기"


def drop_label(intent: QueryIntent, axis: DropAxis) -> str:
    if axis == "region":
        return _WIDEN_REGION_LABEL
    return f"{_axis_noun(intent, axis)} 조건 풀기"


def _axis_noun(intent: QueryIntent, axis: DropAxis) -> str:
    if axis == "crowd":
        return "한적" if intent.crowdPreference == "quiet" else "유명한 곳"
    if axis == "indoor":
        return "실내"
    if axis == "near":
        return "내 근처"
    return category_noun(intent)


def category_noun(intent: QueryIntent) -> str:
    return intent.categoryKeywords[0] if intent.categoryKeywords else "분위기"


def releasable_axes(
    intent: QueryIntent,
    axes: frozenset[DropAxis] = ALL_AXES,
    *,
    has_coords: bool,
) -> list[DropAxis]:
    engaged = _engaged(intent)
    return [
        axis
        for axis in _DROP_ORDER
        if axis in axes
        and engaged[axis]
        and not refine_service.drop_leaves_named_place_only(intent, axis, has_coords=has_coords)
    ]


def derive_for_zero(
    intent: QueryIntent,
    *,
    has_coords: bool,
    axes: frozenset[DropAxis] = ALL_AXES,
) -> list[Suggestion]:
    return [
        Suggestion(label=drop_label(intent, axis), patch=RefinePatch(drop=axis))
        for axis in releasable_axes(intent, axes, has_coords=has_coords)
    ][:MAX_SUGGESTIONS]


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
    releasable = _releasable_axis(intent, axes, has_coords=has_coords)
    if result_count < THIN_RESULT_COUNT and releasable is not None:
        chips.insert(0, Suggestion(label="조건 하나 풀기", patch=RefinePatch(drop=releasable)))
    return chips[:MAX_SUGGESTIONS]


def _releasable_axis(
    intent: QueryIntent, axes: frozenset[DropAxis], *, has_coords: bool
) -> DropAxis | None:
    return next(iter(releasable_axes(intent, axes, has_coords=has_coords)), None)


def _engaged(intent: QueryIntent) -> dict[DropAxis, bool]:
    return {
        "crowd": intent.crowdPreference != "any",
        "indoor": intent.indoorOnly,
        "category": bool(intent.categoryKeywords or intent.moodHints),
        "near": intent.nearMe,
        "region": bool(intent.regionHints),
    }
