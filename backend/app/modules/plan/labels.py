from __future__ import annotations

_CATEGORY_LABELS = {
    "attraction": "관광지",
    "food": "음식점",
    "cafe": "카페",
    "leisure": "레저",
    "shopping": "쇼핑",
}


def category_label(raw: str | None) -> str | None:
    if raw is None:
        return None
    return _CATEGORY_LABELS.get(raw, raw)
