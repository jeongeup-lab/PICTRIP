from __future__ import annotations

from app.modules.agent.schemas import DropAxis, QueryIntent, RefinePatch, Suggestion

MAX_SUGGESTIONS = 3
THIN_RESULT_COUNT = 5
_DROP_ORDER: tuple[DropAxis, ...] = ("crowd", "indoor", "category", "near", "region")


def derive(intent: QueryIntent, *, has_coords: bool, result_count: int) -> list[Suggestion]:
    if intent.festivalOnly:
        return []
    chips: list[Suggestion] = []
    if intent.crowdPreference == "any":
        chips.append(Suggestion(label="사람 적은 곳만", patch=RefinePatch(crowdPreference="quiet")))
    elif intent.crowdPreference == "quiet":
        chips.append(
            Suggestion(label="유명한 곳으로", patch=RefinePatch(crowdPreference="popular"))
        )
    if not intent.indoorOnly:
        chips.append(Suggestion(label="실내만", patch=RefinePatch(indoorOnly=True)))
    if has_coords and not intent.nearMe:
        chips.append(Suggestion(label="가까운 순으로", patch=RefinePatch(nearMe=True)))
    if result_count < THIN_RESULT_COUNT and (axis := _narrowest_axis(intent)) is not None:
        chips.insert(0, Suggestion(label="조건 하나 풀기", patch=RefinePatch(drop=axis)))
    return chips[:MAX_SUGGESTIONS]


def _narrowest_axis(intent: QueryIntent) -> DropAxis | None:
    engaged: dict[DropAxis, bool] = {
        "crowd": intent.crowdPreference != "any",
        "indoor": intent.indoorOnly,
        "category": bool(intent.categoryKeywords or intent.moodHints),
        "near": intent.nearMe,
        "region": bool(intent.regionHints),
    }
    return next((axis for axis in _DROP_ORDER if engaged[axis]), None)
