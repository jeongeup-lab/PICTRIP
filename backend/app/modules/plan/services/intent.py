from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.modules.plan.llm import generate_json

_SYSTEM = (
    "너는 한국 국내여행 도우미의 조건 추출기다. 대화에서 여행 조건을 추출해 JSON으로만 답한다. "
    "region은 시·군 단위 국내 지명 하나(예: 강릉, 전주, 제주). 사용자가 지역을 말하지 않았으면 null. "
    "days는 여행 일수(당일치기=1, 1박 2일=2, 2박 3일=3). 말하지 않았으면 null. "
    "party는 동행(혼자/커플/친구/가족/부모님 등), themes는 취향 키워드 목록, "
    "mobility는 이동수단(walk=뚜벅이/도보, transit=대중교통, car=자차). "
    "이전 추출값이 주어지면 새 메시지로 갱신하되, 언급되지 않은 값은 유지한다."
)

_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "region": {"type": "STRING", "nullable": True},
        "days": {"type": "INTEGER", "nullable": True},
        "party": {"type": "STRING", "nullable": True},
        "themes": {"type": "ARRAY", "items": {"type": "STRING"}},
        "mobility": {
            "type": "STRING",
            "enum": ["walk", "transit", "car"],
            "nullable": True,
        },
    },
    "required": ["themes"],
}

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


def _clamp_days(raw: Any) -> int | None:
    try:
        days = int(raw)
    except (TypeError, ValueError):
        return None
    if days < 1:
        return None
    return min(days, _MAX_DAYS)


async def extract_intent(
    *, previous: dict[str, Any] | None, messages: list[str]
) -> PlanIntent | None:
    user_parts = []
    if previous:
        user_parts.append(f"이전 추출값: {previous}")
    user_parts.append("대화 메시지(오래된 것부터):")
    user_parts.extend(f"- {m}" for m in messages[-6:])

    raw = await generate_json(
        system=_SYSTEM,
        user="\n".join(user_parts),
        schema=_SCHEMA,
        temperature=0.1,
    )
    if raw is None:
        return None

    region = raw.get("region")
    mobility = raw.get("mobility")
    themes = raw.get("themes")
    return PlanIntent(
        region=str(region).strip() or None if isinstance(region, str) else None,
        days=_clamp_days(raw.get("days")),
        party=str(raw["party"]).strip() or None if isinstance(raw.get("party"), str) else None,
        themes=[str(t) for t in themes if str(t).strip()] if isinstance(themes, list) else [],
        mobility=mobility if mobility in ("walk", "transit", "car") else None,
    )
