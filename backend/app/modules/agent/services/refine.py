from __future__ import annotations

from app.modules.agent.schemas import DropAxis, QueryIntent, RefinePatch

_DROP_FIELDS: dict[DropAxis, dict[str, object]] = {
    "crowd": {"crowdPreference": "any"},
    "indoor": {"indoorOnly": False},
    "near": {"nearMe": False},
    "region": {"regionHints": []},
    "category": {"categoryKeywords": [], "moodHints": []},
}


def apply_patch(intent: QueryIntent, patch: RefinePatch | None) -> QueryIntent:
    if patch is None:
        return intent
    changes: dict[str, object] = {}
    if patch.crowdPreference is not None:
        changes["crowdPreference"] = patch.crowdPreference
    if patch.indoorOnly is not None:
        changes["indoorOnly"] = patch.indoorOnly
    if patch.nearMe is not None:
        changes["nearMe"] = patch.nearMe
    if patch.drop is not None:
        changes.update(_cleared(patch.drop))
    return intent.model_copy(update=changes)


def named_place_is_the_only_constraint(
    intent: QueryIntent, *, keywords: list[str], prefixes: list[str], near: bool
) -> bool:
    return bool(
        intent.namedPlaces
        and not keywords
        and not prefixes
        and not near
        and not intent.moodHints
        and not intent.indoorOnly
        and intent.crowdPreference == "any"
    )


def drop_leaves_named_place_only(intent: QueryIntent, axis: DropAxis, *, has_coords: bool) -> bool:
    dropped = apply_patch(intent, RefinePatch(drop=axis))
    return named_place_is_the_only_constraint(
        dropped,
        keywords=list(dropped.categoryKeywords),
        prefixes=list(dropped.regionHints),
        near=dropped.nearMe and has_coords,
    )


def _cleared(axis: DropAxis) -> dict[str, object]:
    return {
        field: list(value) if isinstance(value, list) else value
        for field, value in _DROP_FIELDS[axis].items()
    }
