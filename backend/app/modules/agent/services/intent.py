from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from app.core.logging import get_logger
from app.modules.agent import llm
from app.modules.agent.errors import AgentIntentUnavailable
from app.modules.agent.schemas import CrowdPreference, ExtractedPlace, QueryIntent

logger = get_logger(__name__)

MAX_QUESTION_CHARS = 500

_SYSTEM_PROMPT = """\
너는 한국 여행지 검색 질문을 구조화하는 도우미다.
사용자의 한 줄 질문을 아래 규칙대로 JSON으로 변환한다. 장소를 추천하지 말고, 질문에 담긴 조건만 뽑는다.

규칙:
- categoryKeywords: 찾는 장소의 종류를 한국어 명사로. 한국관광공사 분류 체계에 나올 법한 일반명사를 쓴다
  (예: "계곡", "해수욕장", "박물관", "미술관", "사찰", "전망대", "수목원", "테마파크").
  질문에 종류가 없으면 빈 배열.
- regionHints: 질문에 나온 지역명 그대로 (예: "제주", "여수", "강릉"). 없으면 빈 배열.
- namedPlaces: 질문이 특정 장소를 이름으로 지목할 때만 채운다 (예: "감천문화마을 근처"). 일반명사는 넣지 않는다.
- crowdPreference: 한적함을 원하면 "quiet", 유명한 곳을 원하면 "popular", 언급이 없으면 "any".
- indoorOnly: 비·더위·추위를 피하거나 실내를 명시하면 true, 아니면 false.
- nearMe: "근처", "가까운", "여기서" 처럼 현재 위치 기준을 요구하면 true, 아니면 false.
- outOfScope: 대한민국 밖의 여행지를 묻는 질문이면 true (예: "파리 가볼 만한 곳"). 국내 질문이면 false.
- outOfScope가 true면 나머지 배열은 모두 비운다.
- 추측으로 조건을 만들어내지 않는다. 질문에 없으면 비운다.
"""

_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "categoryKeywords": {"type": "ARRAY", "items": {"type": "STRING"}},
        "regionHints": {"type": "ARRAY", "items": {"type": "STRING"}},
        "namedPlaces": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "name": {"type": "STRING"},
                    "nameKo": {"type": "STRING", "nullable": True},
                    "placeType": {
                        "type": "STRING",
                        "enum": ["attraction", "restaurant", "cafe", "hotel", "region"],
                    },
                    "regionHint": {"type": "STRING", "nullable": True},
                },
                "required": ["name", "placeType"],
            },
        },
        "crowdPreference": {"type": "STRING", "enum": ["quiet", "any", "popular"]},
        "indoorOnly": {"type": "BOOLEAN"},
        "nearMe": {"type": "BOOLEAN"},
        "outOfScope": {"type": "BOOLEAN"},
    },
    "required": [
        "categoryKeywords",
        "regionHints",
        "crowdPreference",
        "indoorOnly",
        "nearMe",
        "outOfScope",
    ],
}


async def extract_intent(question: str) -> QueryIntent:
    data = await llm.get_client().generate_json(
        system=_SYSTEM_PROMPT,
        user_text=question.strip()[:MAX_QUESTION_CHARS],
        response_schema=_RESPONSE_SCHEMA,
    )
    if not isinstance(data, dict):
        raise AgentIntentUnavailable()
    intent = QueryIntent(
        categoryKeywords=_strings(data.get("categoryKeywords")),
        regionHints=_strings(data.get("regionHints")),
        namedPlaces=_places(data.get("namedPlaces")),
        crowdPreference=_crowd(data.get("crowdPreference")),
        indoorOnly=bool(data.get("indoorOnly")),
        nearMe=bool(data.get("nearMe")),
        outOfScope=bool(data.get("outOfScope")),
    )
    logger.info(
        "agent.intent.done",
        categories=len(intent.categoryKeywords),
        regions=len(intent.regionHints),
        named=len(intent.namedPlaces),
        crowd=intent.crowdPreference,
        out_of_scope=intent.outOfScope,
    )
    return intent


def _strings(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    seen: list[str] = []
    for item in raw:
        if isinstance(item, str) and (cleaned := item.strip()) and cleaned not in seen:
            seen.append(cleaned)
    return seen


def _places(raw: Any) -> list[ExtractedPlace]:
    if not isinstance(raw, list):
        return []
    places: list[ExtractedPlace] = []
    for item in raw:
        try:
            places.append(ExtractedPlace.model_validate(item))
        except ValidationError:
            continue
    return places


def _crowd(raw: Any) -> CrowdPreference:
    if raw == "quiet":
        return "quiet"
    if raw == "popular":
        return "popular"
    return "any"
