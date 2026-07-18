from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_MAX_DAYS = 3


@dataclass
class PlanIntent:
    region: str | None = None
    days: int | None = None
    party: str | None = None
    themes: list[str] | None = None
    mobility: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "region": self.region,
            "days": self.days,
            "party": self.party,
            "themes": self.themes or [],
            "mobility": self.mobility,
        }


def clamp_days(raw: Any) -> int | None:
    try:
        days = int(raw)
    except (TypeError, ValueError):
        return None
    if days < 1:
        return None
    return min(days, _MAX_DAYS)
