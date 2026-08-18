from __future__ import annotations

from collections.abc import Callable

from app.modules.agent.schemas import MAX_KEYWORDS, QueryIntent

HUNGER_WORDS = (
    "배고파",
    "배고프",
    "배가 고",
    "출출",
    "허기",
    "시장해",
    "먹고 싶",
    "뭐 먹",
    "먹을 거",
    "먹을거",
    "밥 먹자",
)
ASKING_ABOUT_ME = ("너 ", "너는", "니가", "당신", "먹었어", "먹었니", "먹었나", "먹었어요")
LODGING_WORDS = frozenset(
    {"호텔", "펜션", "모텔", "리조트", "게스트하우스", "숙소", "민박", "콘도", "호스텔"}
)
UNSETTLED_TASKS = ("smalltalk", "unsupported")


def hungry(question: str) -> bool:
    """자기 배고픔은 맛집 요청이다. 상대에게 묻는 말은 아니다.

    "아 배고파" 를 smalltalk 으로 두면 대화가 끊긴다. "너 밥 먹었어?" 는 그대로 잡담이다.
    """
    asked = question.strip()
    if any(word in asked for word in ASKING_ABOUT_ME):
        return False
    return any(word in asked for word in HUNGER_WORDS)


def _as_food_search(intent: QueryIntent) -> QueryIntent:
    keywords = list(intent.categoryKeywords)
    if "맛집" not in keywords:
        keywords.insert(0, "맛집")
    return intent.model_copy(update={"task": "search", "categoryKeywords": keywords[:MAX_KEYWORDS]})


def _hunger(intent: QueryIntent, question: str, *, guessed: bool) -> QueryIntent:
    if not hungry(question):
        return intent
    if not guessed and intent.task not in UNSETTLED_TASKS:
        return intent
    return _as_food_search(intent)


def _lodging(intent: QueryIntent, question: str, *, guessed: bool) -> QueryIntent:
    """숙소만 찾는 질문은 우리가 답하지 않는다.

    KTO 에 숙박(contentTypeId 32)이 있어도 서빙하지 않기로 한 제품 결정이다.
    프롬프트의 "숙소 예약" 문구는 예약만 걸러서 "제주 호텔 추천해줘" 가 검색으로 샜다.
    다른 유형을 함께 물으면 그쪽을 살린다 — "호텔 근처 카페" 는 카페 검색이다.
    """
    if intent.task != "search" or not intent.categoryKeywords:
        return intent
    if not all(keyword in LODGING_WORDS for keyword in intent.categoryKeywords):
        return intent
    return QueryIntent(task="unsupported")


Correction = Callable[[QueryIntent, str, bool], QueryIntent]

CORRECTIONS: tuple[Correction, ...] = (
    lambda intent, question, guessed: _hunger(intent, question, guessed=guessed),
    lambda intent, question, guessed: _lodging(intent, question, guessed=guessed),
)


def apply_corrections(intent: QueryIntent, question: str, *, guessed: bool = False) -> QueryIntent:
    """모델이 뽑은 의도를 결정적으로 고친다.

    프롬프트는 266케이스 전역에 걸린 지점이라 한 줄만 바꿔도 전체를 다시 재야 한다.
    여기 규칙은 좁고 결정적이라 그 규칙을 타는 테스트만 다시 돌리면 된다.

    `guessed` 는 폴백이 만든 의도라는 뜻이다 — task 를 신뢰할 수 없다.
    """
    for correct in CORRECTIONS:
        intent = correct(intent, question, guessed)
    return intent
