from __future__ import annotations

import re
from dataclasses import dataclass
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
from app.web.errors import RateLimited

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
  먹고 마시는 곳을 물으면 그 말을 그대로 넣는다 — "맛집", "식당", "카페", "커피".
  분류 체계에 없어 보여도 빼지 말고 넣는다.
- 동반자를 말하면(아이랑 · 애들이랑 · 가족이) 그에 맞는 장소 종류를 categoryKeywords 에 편다 —
  "테마파크", "동물원", "수족관", "어린이공원", "체험농장". 단 다른 유형이나 분위기를
  함께 말했으면 그쪽을 쓰고 동반자는 무시한다 ("아이랑 갈 바다" 는 바다다).
- regionHints: 질문에 나온 지역명 그대로 (예: "제주", "여수", "강릉"). 없으면 빈 배열.
- namedPlaces: 질문이 특정 장소를 이름으로 지목할 때만 채운다 (예: "감천문화마을 근처"). 일반명사는 넣지 않는다.
  역·터미널·랜드마크도 이름이면 넣는다 ("대천역 근처" → 대천역).
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


@dataclass(frozen=True, slots=True)
class IntentOutcome:
    intent: QueryIntent
    fallback: bool


async def resolve_intent(
    question: str,
    *,
    prior: QueryIntent | None = None,
    prior_spots: list[str] | None = None,
) -> IntentOutcome:
    try:
        asked = (
            await extract_intent(question, prior=prior, prior_spots=prior_spots)
            if prior is not None or prior_spots
            else await extract_intent(question)
        )
    except (AgentIntentUnavailable, RateLimited) as exc:
        guessed = _carried(fallback_intent(question), prior)
        logger.warning(
            "agent.intent.fallback",
            code=exc.code,
            categories=len(guessed.categoryKeywords),
            regions=len(guessed.regionHints),
            moods=len(guessed.moodHints),
            crowd=guessed.crowdPreference,
            indoor=guessed.indoorOnly,
            near=guessed.nearMe,
        )
        return IntentOutcome(intent=guessed, fallback=True)
    return IntentOutcome(intent=asked, fallback=False)


def _carried(guessed: QueryIntent, prior: QueryIntent | None) -> QueryIntent:
    if prior is None:
        return guessed
    return guessed.model_copy(
        update={
            "categoryKeywords": guessed.categoryKeywords or list(prior.categoryKeywords),
            "regionHints": guessed.regionHints or list(prior.regionHints),
            "moodHints": guessed.moodHints or list(prior.moodHints),
            "crowdPreference": (
                guessed.crowdPreference
                if guessed.crowdPreference != "any"
                else prior.crowdPreference
            ),
        }
    )


NEAR_WORDS = ("근처", "가까운", "가까이", "여기서", "여기 주변", "주변", "내 위치", "인근")
QUIET_WORDS = ("한적", "조용", "사람 적", "사람이 적", "붐비지", "북적이지", "여유")
POPULAR_WORDS = ("핫플", "유명", "인기", "붐비는", "사람 많")
INDOOR_WORDS = (
    "실내",
    "비 올",
    "비올",
    "비 오는",
    "비오는",
    "비가",
    "우천",
    "장마",
    "더위",
    "폭염",
    "추위",
    "한파",
    "미세먼지",
)
CATEGORY_WORDS: dict[str, str] = {
    "맛집": "맛집",
    "밥집": "맛집",
    "먹거리": "맛집",
    "먹을": "맛집",
    "음식": "맛집",
    "식당": "식당",
    "카페": "카페",
    "커피": "카페",
    "찻집": "카페",
    "디저트": "카페",
    "박물관": "박물관",
    "미술관": "미술관",
    "사찰": "사찰",
    "템플스테이": "사찰",
    "전망대": "전망대",
    "수목원": "수목원",
    "식물원": "수목원",
    "테마파크": "테마파크",
    "놀이공원": "테마파크",
    "놀이동산": "테마파크",
    "해수욕장": "해수욕장",
    "계곡": "계곡",
    "폭포": "폭포",
    "온천": "온천",
    "전통시장": "전통시장",
    "재래시장": "전통시장",
    "수족관": "수족관",
    "아쿠아리움": "수족관",
    "동물원": "동물원",
    "공원": "공원",
    "산책로": "산책로",
    "둘레길": "둘레길",
    "트레킹": "둘레길",
    "케이블카": "케이블카",
    "출렁다리": "출렁다리",
    "체험마을": "체험마을",
    "고택": "고택",
    "역사유적": "역사유적",
    "유적지": "역사유적",
    "글램핑": "글램핑",
    "캠핑장": "캠핑장",
    "캠핑": "캠핑장",
}
MOOD_WORDS: dict[str, Mood] = {
    "바다": "sea",
    "바닷": "sea",
    "해변": "sea",
    "해안": "sea",
    "오션": "sea",
    "숲": "mountain",
    "등산": "mountain",
    "산림": "mountain",
    "산속": "mountain",
    "산길": "mountain",
    "호수": "lake",
    "저수지": "lake",
    "호반": "lake",
    "한옥": "hanok",
    "고궁": "hanok",
    "궁궐": "hanok",
    "전통": "hanok",
    "야경": "night",
    "노을": "night",
    "일몰": "night",
    "야간": "night",
    "골목": "street",
}
MOOD_TOKENS: dict[str, Mood] = {
    "산": "mountain",
    "섬": "island",
    "밤": "night",
    "거리": "street",
}
REGION_STOPWORDS = frozenset(
    {
        "심심",
        "뭐해",
        "누구",
        "고마",
        "감사",
        "미안",
        "반가",
        "추천",
        "추천지",
        "알려",
        "알려줘",
        "부탁",
        "해줘",
        "어디",
        "어디야",
        "어딘가",
        "근처",
        "가까운",
        "여기",
        "여기서",
        "거기",
        "그곳",
        "그쪽",
        "저기",
        "저곳",
        "이곳",
        "주변",
        "인근",
        "좋은",
        "좋을",
        "있는",
        "있을",
        "없나",
        "만한",
        "가볼",
        "가볼만한",
        "갈만한",
        "즐길",
        "볼거리",
        "놀거리",
        "구경",
        "산책",
        "마을",
        "근교",
        "그리고",
        "아니면",
        "나들이",
        "데이트",
        "힐링",
        "코스",
        "장소",
        "여행",
        "여행지",
        "관광",
        "관광지",
        "오늘",
        "내일",
        "모레",
        "주말",
        "요즘",
        "지금",
        "아침",
        "점심",
        "저녁",
        "하루",
        "당일치기",
        "날씨",
        "사람",
        "사람들",
        "우리",
        "아이",
        "아이랑",
        "애들",
        "가족",
        "친구",
        "연인",
        "커플",
        "혼자",
        "부모님",
        "아무거나",
        "진짜",
        "정말",
        "완전",
        "그냥",
        "조금",
        "살짝",
        "고마워",
        "안녕",
        "반가워",
        "뭔가",
        "어떤",
        "무슨",
        "어때",
        "예쁜",
        "이쁜",
        "멋진",
        "분위기",
        "사진",
        "느낌",
        "스팟",
        "명소",
        "유명",
        "유명한",
        "한적",
        "조용",
        "조용한",
        "실내",
        "실외",
        "야외",
        "시원한",
        "따뜻한",
    }
)
JOSA_SUFFIXES = (
    "에서는",
    "으로는",
    "에서",
    "으로",
    "까지",
    "부터",
    "이랑",
    "에는",
    "에게",
    "이나",
    "라도",
    "은",
    "는",
    "이",
    "가",
    "을",
    "를",
    "도",
    "만",
    "과",
    "와",
    "랑",
    "의",
    "에",
    "쪽",
)
VERB_TAIL_CHARS = frozenset("요어아까죠지네다게며면고만한할은는워줘봐야세니이")
MIN_REGION_TOKEN_CHARS = 2
MAX_REGION_TOKEN_CHARS = 6
MAX_FALLBACK_REGIONS = 3
_HANGUL_SPLIT = re.compile(r"[^가-힣]+")


UNSUPPORTED_WORDS = (
    "예약",
    "티켓",
    "항공",
    "비행기",
    "숙소",
    "호텔",
    "펜션",
    "길찾기",
    "가는 법",
    "가는법",
    "교통",
    "지하철",
    "버스",
    "기차",
    "렌트",
    "날씨",
    "환율",
    "주식",
    "코인",
    "병원",
    "약국",
    "은행",
    "편의점",
    "주유소",
    "마트",
    "관공서",
    "선물",
    "일정 짜",
    "코스 짜",
    "번역",
)
SMALLTALK_WORDS = (
    "안녕",
    "고마워",
    "감사",
    "반가",
    "잘가",
    "미안",
    "사랑해",
    "심심",
    "뭐해",
    "누구야",
    "이름이 뭐",
    "ㅋㅋ",
    "ㅎㅎ",
    "ㅇㅇ",
)
OVERSEAS_WORDS = (
    "파리",
    "도쿄",
    "오사카",
    "교토",
    "후쿠오카",
    "삿포로",
    "뉴욕",
    "런던",
    "방콕",
    "다낭",
    "하노이",
    "발리",
    "하와이",
    "괌",
    "세부",
    "상하이",
    "베이징",
    "타이베이",
    "홍콩",
    "싱가포르",
    "로마",
    "바르셀로나",
    "시드니",
    "두바이",
)


def fallback_intent(question: str) -> QueryIntent:
    asked = question.strip()[:MAX_QUESTION_CHARS]
    if not asked:
        return QueryIntent()
    if _mentions(asked, OVERSEAS_WORDS):
        return QueryIntent(outOfScope=True)
    if _mentions(asked, UNSUPPORTED_WORDS):
        return QueryIntent(task="unsupported")
    residual = asked
    categories: list[str] = []
    for trigger in _by_length(CATEGORY_WORDS):
        if trigger in residual:
            residual = residual.replace(trigger, " ")
            _add(categories, CATEGORY_WORDS[trigger])
    moods: list[Mood] = []
    for trigger in _by_length(MOOD_WORDS):
        if trigger in residual:
            residual = residual.replace(trigger, " ")
            _add(moods, MOOD_WORDS[trigger])
    near = _mentions(asked, NEAR_WORDS)
    indoor = _mentions(asked, INDOOR_WORDS)
    crowd = _crowd_preference(asked)
    for trigger in (*NEAR_WORDS, *INDOOR_WORDS, *QUIET_WORDS, *POPULAR_WORDS):
        residual = residual.replace(trigger, " ")
    regions = _region_hints(residual, moods)
    if not categories and not moods and not regions and _mentions(asked, SMALLTALK_WORDS):
        return QueryIntent(task="smalltalk")
    return QueryIntent(
        categoryKeywords=categories[:MAX_KEYWORDS],
        regionHints=regions,
        moodHints=moods,
        crowdPreference=crowd,
        indoorOnly=indoor,
        nearMe=near,
    )


def _by_length(words: dict[str, Any]) -> list[str]:
    return sorted(words, key=len, reverse=True)


def _add(picked: list[Any], value: Any) -> None:
    if value not in picked:
        picked.append(value)


def _mentions(asked: str, words: tuple[str, ...]) -> bool:
    return any(word in asked for word in words)


def _crowd_preference(asked: str) -> CrowdPreference:
    if _mentions(asked, QUIET_WORDS):
        return "quiet"
    if _mentions(asked, POPULAR_WORDS):
        return "popular"
    return "any"


def _region_hints(residual: str, moods: list[Mood]) -> list[str]:
    hints: list[str] = []
    for raw in _HANGUL_SPLIT.split(residual):
        word = raw.strip()
        if not word:
            continue
        stripped = _without_josa(word)
        if (code := MOOD_TOKENS.get(stripped) or MOOD_TOKENS.get(word)) is not None:
            _add(moods, code)
            continue
        token = stripped if len(stripped) >= MIN_REGION_TOKEN_CHARS else word
        if _is_region_candidate(token) and len(hints) < MAX_FALLBACK_REGIONS:
            _add(hints, token)
    return hints[:MAX_REGION_HINTS]


def _without_josa(token: str) -> str:
    for suffix in JOSA_SUFFIXES:
        if token.endswith(suffix) and len(token) > len(suffix):
            return token[: -len(suffix)]
    return token


def _is_region_candidate(token: str) -> bool:
    if not MIN_REGION_TOKEN_CHARS <= len(token) <= MAX_REGION_TOKEN_CHARS:
        return False
    if token in JOSA_SUFFIXES:
        return False
    if any(token.startswith(word) for word in REGION_STOPWORDS):
        return False
    return token[-1] not in VERB_TAIL_CHARS


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
