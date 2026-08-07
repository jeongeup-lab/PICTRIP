from __future__ import annotations

from typing import Any, get_args

from pydantic import ValidationError

from app.core.logging import get_logger
from app.modules.agent import llm
from app.modules.agent.errors import AgentIntentUnavailable
from app.modules.agent.schemas import (
    MAX_KEYWORDS,
    MAX_NAMED_PLACES,
    MAX_REGION_HINTS,
    MAX_TEXT_CHARS,
    MAX_TITLE_CHARS,
    CrowdPreference,
    DetailField,
    ExtractedPlace,
    Mood,
    QueryIntent,
    TaskKind,
)

logger = get_logger(__name__)

MAX_QUESTION_CHARS = 500

_SYSTEM_PROMPT = """\
너는 한국 여행 앱의 대화를 구조화하는 도우미다.
사용자의 한 줄 입력을 아래 규칙대로 JSON으로 변환한다. 장소를 추천하지 말고, 입력에 담긴 것만 뽑는다.

먼저 task 를 고른다.
- search: 조건에 맞는 여행지를 찾아달라는 말 (예: "제주 한적한 바다", "비 오는 날 실내").
- detail: 이미 이야기한 특정 장소 하나에 대해 사실을 묻는 말
  (예: "영업시간 몇시야", "쉬는 날 있어", "주차 되나", "입장료 얼마", "어떤 곳이야").
  직전 결과나 지금 고른 장소가 있어야 성립한다. targetPlace 에 그 장소 이름을 그대로 넣고,
  detailFields 에 묻는 것을 고른다 — hours(영업·이용시간) · closed(휴무일) · parking(주차) ·
  contact(전화·문의) · fee(요금·입장료) · overview(어떤 곳인지).
- smalltalk: 인사·감탄·맞장구처럼 찾아달라는 요구가 없는 말 (예: "안녕", "고마워", "ㅇㅇ").
- unsupported: 이 앱이 못 하는 요구 — 일정·코스 짜기, 예약, 길찾기·교통편, 날씨, 숙소 예약,
  그리고 관광지가 아닌 시설 찾기(병원·약국·은행·편의점·주유소·관공서·마트).
task 가 search 가 아니면 아래 조건 필드는 모두 비운다. 애매하면 search 로 둔다.

규칙:
- categoryKeywords: 찾는 장소의 종류를 한국어 명사로. 한국관광공사 분류 체계에 나올 법한 일반명사를 쓴다
  (예: "계곡", "해수욕장", "박물관", "미술관", "사찰", "전망대", "수목원", "테마파크").
  질문에 종류가 없으면 빈 배열.
  바다·산·숲·호수·섬·한옥·고궁·야경·골목은 여기에 넣지 않는다 — moodHints 가 맡는다.
- 동반자를 말하면(아이랑 · 애들이랑 · 가족이) 그에 맞는 장소 종류를 categoryKeywords 에 편다 —
  "테마파크", "동물원", "수족관", "어린이공원", "체험농장". 단 다른 유형이나 분위기를
  함께 말했으면 그쪽을 쓰고 동반자는 무시한다 ("아이랑 갈 바다" 는 바다다).
- regionHints: 질문에 나온 지역명 그대로 (예: "제주", "여수", "강릉"). 없으면 빈 배열.
- namedPlaces: 질문이 특정 장소를 이름으로 지목할 때만 채운다 (예: "감천문화마을 근처"). 일반명사는 넣지 않는다.
- crowdPreference: 한적함을 원하면 "quiet", 유명한 곳을 원하면 "popular", 언급이 없으면 "any".
- indoorOnly: 비·더위·추위를 피하거나 실내를 명시하면 true, 아니면 false.
- nearMe: "근처", "가까운", "여기서" 처럼 현재 위치 기준을 요구하면 true, 아니면 false.
- moodHints: 분위기를 지목하면 아래 코드 중에서만 고른다 — sea(바다), mountain(산·숲),
  lake(호수), island(섬), hanok(한옥·고궁), night(야경), street(도시 골목). 없으면 빈 배열.
- festivalOnly: 축제·행사·페스티벌을 찾는 질문이면 true, 아니면 false.
- outOfScope: 대한민국 밖의 여행지를 묻는 질문이면 true (예: "파리 가볼 만한 곳"). 국내 질문이면 false.
- outOfScope가 true면 나머지 배열은 모두 비운다.
- 추측으로 조건을 만들어내지 않는다. 질문에 없으면 비운다.

이어지는 질문이면 직전 대화가 함께 주어진다. 그때는 아래를 지킨다.
- 직전 조건은 사용자가 바꾸지 않는 한 그대로 유지한다. "더 한적한 곳" 은 직전
  지역·유형을 그대로 두고 crowdPreference 만 quiet 로 바꾸는 것이다.
- 사용자가 새 지역이나 새 유형을 말하면 그 축만 갈아끼운다. 나머지는 유지한다.
- "거기 근처" · "그 옆에" · "여기 근처" 처럼 앞 결과 한 곳을 중심으로 주변을 물으면
  aroundOrigin 을 true 로 둔다. 그 위에서 어느 곳인지 이름으로 특정할 수 있으면
  originPlace 에 직전 결과 목록의 그 이름을 그대로 넣고, 특정할 수 없으면 비운다. originPlace 를 채웠으면 그 장소는 namedPlaces 에 넣지
  않는다 — 찾는 대상이 아니라 기준점이기 때문이다.
- 화제가 완전히 바뀌면 직전 조건을 버린다.
"""

_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "task": {
            "type": "STRING",
            "enum": ["search", "detail", "smalltalk", "unsupported"],
        },
        "targetPlace": {"type": "STRING", "nullable": True},
        "detailFields": {
            "type": "ARRAY",
            "items": {"type": "STRING", "enum": list(get_args(DetailField))},
        },
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
        "moodHints": {
            "type": "ARRAY",
            "items": {"type": "STRING", "enum": list(get_args(Mood))},
        },
        "festivalOnly": {"type": "BOOLEAN"},
        "originPlace": {"type": "STRING", "nullable": True},
        "aroundOrigin": {"type": "BOOLEAN"},
        "indoorOnly": {"type": "BOOLEAN"},
        "nearMe": {"type": "BOOLEAN"},
        "outOfScope": {"type": "BOOLEAN"},
    },
    "required": [
        "task",
        "categoryKeywords",
        "regionHints",
        "crowdPreference",
        "moodHints",
        "festivalOnly",
        "indoorOnly",
        "nearMe",
        "outOfScope",
    ],
}

_MOOD_CODES: tuple[Mood, ...] = get_args(Mood)
_TASKS: tuple[TaskKind, ...] = get_args(TaskKind)
_DETAIL_FIELDS: tuple[DetailField, ...] = get_args(DetailField)


def _context_block(prior: QueryIntent | None, spots: list[str]) -> str:
    lines: list[str] = []
    if prior is not None:
        lines.append(f"직전 조건: {prior.model_dump_json(exclude_defaults=True)}")
    if spots:
        lines.append("직전 결과: " + " · ".join(spots))
    return "\n".join(lines)


async def extract_intent(
    question: str,
    *,
    prior: QueryIntent | None = None,
    prior_spots: list[str] | None = None,
) -> QueryIntent:
    block = _context_block(prior, prior_spots or [])
    asked = question.strip()[:MAX_QUESTION_CHARS]
    data = await llm.get_client().generate_json(
        system=_SYSTEM_PROMPT,
        user_text=f"{block}\n\n이번 질문: {asked}" if block else asked,
        response_schema=_RESPONSE_SCHEMA,
    )
    if not isinstance(data, dict):
        raise AgentIntentUnavailable()
    intent = QueryIntent(
        task=_task(data.get("task")),
        targetPlace=_text(data.get("targetPlace")),
        detailFields=_detail_fields(data.get("detailFields")),
        categoryKeywords=_strings(data.get("categoryKeywords"))[:MAX_KEYWORDS],
        regionHints=_strings(data.get("regionHints"))[:MAX_REGION_HINTS],
        namedPlaces=_places(data.get("namedPlaces"))[:MAX_NAMED_PLACES],
        crowdPreference=_crowd(data.get("crowdPreference")),
        moodHints=_moods(data.get("moodHints")),
        festivalOnly=bool(data.get("festivalOnly")),
        originPlace=_text(data.get("originPlace")),
        aroundOrigin=bool(data.get("aroundOrigin")),
        indoorOnly=bool(data.get("indoorOnly")),
        nearMe=bool(data.get("nearMe")),
        outOfScope=bool(data.get("outOfScope")),
    )
    logger.info(
        "agent.intent.done",
        with_context=bool(block),
        categories=len(intent.categoryKeywords),
        regions=len(intent.regionHints),
        named=len(intent.namedPlaces),
        crowd=intent.crowdPreference,
        moods=len(intent.moodHints),
        out_of_scope=intent.outOfScope,
        task=intent.task,
    )
    return intent


def _strings(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    seen: list[str] = []
    for item in raw:
        if (
            isinstance(item, str)
            and (cleaned := item.strip()[:MAX_TEXT_CHARS])
            and cleaned not in seen
        ):
            seen.append(cleaned)
    return seen


def _places(raw: Any) -> list[ExtractedPlace]:
    if not isinstance(raw, list):
        return []
    places: list[ExtractedPlace] = []
    for item in raw:
        try:
            places.append(ExtractedPlace.model_validate(_clipped(item)))
        except ValidationError:
            continue
    return places


def _clipped(item: Any) -> Any:
    if not isinstance(item, dict):
        return item
    return {
        key: value[:MAX_TEXT_CHARS] if isinstance(value, str) else value
        for key, value in item.items()
    }


def _moods(raw: Any) -> list[Mood]:
    if not isinstance(raw, list):
        return []
    picked: list[Mood] = []
    for item in raw:
        if item in _MOOD_CODES and item not in picked:
            picked.append(item)
    return picked


def _task(raw: Any) -> TaskKind:
    return raw if raw in _TASKS else "search"


def _detail_fields(raw: Any) -> list[DetailField]:
    if not isinstance(raw, list):
        return []
    picked: list[DetailField] = []
    for item in raw:
        if item in _DETAIL_FIELDS and item not in picked:
            picked.append(item)
    return picked


def _crowd(raw: Any) -> CrowdPreference:
    if raw == "quiet":
        return "quiet"
    if raw == "popular":
        return "popular"
    return "any"


def _text(raw: Any) -> str | None:
    if not isinstance(raw, str):
        return None
    cleaned = raw.strip()[:MAX_TITLE_CHARS]
    return cleaned or None
