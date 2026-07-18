from __future__ import annotations

from typing import Any

from app.modules.plan.llm import generate_json
from app.modules.plan.schemas import PlanDay
from app.modules.plan.services.intent import PlanIntent

_SYSTEM = (
    "너는 한국 국내여행 플래너의 카피라이터다. 완성된 일정을 보고 JSON으로만 답한다. "
    "title은 지역과 분위기가 드러나는 15자 이내 제목(예: '강릉 당일치기, 바다와 커피'). "
    "summary는 동선의 특징과 선정 이유를 담은 1~2문장, 해요체. "
    "replyText는 일정을 건네며 채팅으로 보낼 1~2문장, 해요체. 과장·이모지 금지. "
    "장소 설명은 주어진 일정 데이터에 있는 사실만 사용한다."
)

_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "title": {"type": "STRING"},
        "summary": {"type": "STRING"},
        "replyText": {"type": "STRING"},
    },
    "required": ["title", "summary", "replyText"],
}

_DAY_LABEL = {1: "당일치기", 2: "1박 2일", 3: "2박 3일"}


def _fallback(intent: PlanIntent) -> dict[str, str]:
    region = intent.region or "국내"
    duration = _DAY_LABEL.get(intent.days or 1, f"{intent.days}일")
    title = f"{region} {duration} 여행"
    return {
        "title": title,
        "summary": "이동 시간을 줄이는 순서로 담았어요. 관광지는 한국관광공사, 맛집과 카페는 네이버 인기 데이터에서 골랐어요.",
        "replyText": f"{region} 일정을 만들었어요. 카드를 눌러 전체 일정을 확인해보세요.",
    }


def _compact(days: list[PlanDay]) -> list[dict[str, Any]]:
    return [
        {
            "day": d.index,
            "slots": [
                {"label": s.label, "type": s.type, "name": s.name, "category": s.category}
                for s in d.slots
            ],
        }
        for d in days
    ]


async def narrate_plan(intent: PlanIntent, days: list[PlanDay]) -> dict[str, str]:
    user = f"여행 조건: {intent.to_dict()}\n일정: {_compact(days)}"
    raw = await generate_json(system=_SYSTEM, user=user, schema=_SCHEMA, temperature=0.7)
    fallback = _fallback(intent)
    if raw is None:
        return fallback
    return {
        "title": str(raw.get("title") or fallback["title"])[:40],
        "summary": str(raw.get("summary") or fallback["summary"]),
        "replyText": str(raw.get("replyText") or fallback["replyText"]),
    }
