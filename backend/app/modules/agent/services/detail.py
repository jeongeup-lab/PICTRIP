from __future__ import annotations

from redis.asyncio import Redis

from app.core.db import AsyncSession
from app.core.logging import get_logger
from app.kto.client import KtoClient
from app.kto.display import t1_display_url
from app.modules.agent.errors import AgentNoResults
from app.modules.agent.schemas import (
    AgentSpotCard,
    AnswerSegment,
    AskResponse,
    AskStep,
    DetailField,
    QueryIntent,
)
from app.modules.spots.services import load_spot_detail
from app.modules.spots.services.rows import SpotDetailRow, SpotIntroRow
from app.web.errors import AppError

logger = get_logger(__name__)

UNKNOWN_HINT = "정보가 아직 없어요"
STALE_HINT = "지금은 확인이 어려워요"
DEFAULT_FIELDS: tuple[DetailField, ...] = ("hours", "closed")
MAX_ANSWERED_FIELDS = 3
FIELD_NOUNS: dict[DetailField, str] = {
    "hours": "이용시간",
    "closed": "쉬는 날",
    "parking": "주차",
    "contact": "문의",
    "fee": "이용요금",
    "overview": "소개",
}
HANGUL_BASE = 0xAC00
HANGUL_LAST = 0xD7A3
JONGSEONG_COUNT = 28
DIGIT_HAS_FINAL: dict[str, bool] = {
    "0": True,
    "1": True,
    "3": True,
    "6": True,
    "7": True,
    "8": True,
    "2": False,
    "4": False,
    "5": False,
    "9": False,
}


def ends_with_consonant(text: str) -> bool:
    tail = text.rstrip()
    if not tail:
        return False
    last = tail[-1]
    if last in DIGIT_HAS_FINAL:
        return DIGIT_HAS_FINAL[last]
    if HANGUL_BASE <= ord(last) <= HANGUL_LAST:
        return (ord(last) - HANGUL_BASE) % JONGSEONG_COUNT != 0
    return False


def fact_sentence(noun: str, value: str) -> str:
    topic = "은" if ends_with_consonant(noun) else "는"
    copula = "이에요" if ends_with_consonant(value) else "예요"
    return f"{noun}{topic} {value}{copula}."


def field_value(intro: SpotIntroRow | None, tel: str | None, field: DetailField) -> str | None:
    if field == "contact":
        return (intro.infocenter if intro else None) or tel
    if intro is None:
        return None
    if field == "hours":
        return intro.usetime
    if field == "closed":
        return intro.restdate
    if field == "parking":
        return intro.parking
    if field == "fee":
        return intro.usefee
    return None


def _asked(intent: QueryIntent) -> list[DetailField]:
    picked = list(dict.fromkeys(intent.detailFields))[:MAX_ANSWERED_FIELDS]
    return picked or list(DEFAULT_FIELDS)


def _sentence(row: SpotDetailRow, field: DetailField) -> list[AnswerSegment]:
    noun = FIELD_NOUNS[field]
    if field == "overview":
        if not row.overview:
            return [AnswerSegment(text=f"{noun} {UNKNOWN_HINT}.")]
        return [AnswerSegment(text=row.overview)]
    value = field_value(row.intro, row.tel, field)
    if not value:
        return [AnswerSegment(text=f"{noun} {UNKNOWN_HINT}.")]
    sentence = fact_sentence(noun, value)
    head, _, tail = sentence.partition(value)
    return [
        AnswerSegment(text=head),
        AnswerSegment(text=value, emphasis=True),
        AnswerSegment(text=tail),
    ]


def _card(row: SpotDetailRow) -> AgentSpotCard:
    return AgentSpotCard(
        contentId=row.content_id,
        title=row.title,
        regionLabel=" ".join(part for part in (row.region_name, row.sigungu_name) if part),
        imageUrl=t1_display_url(row.first_image_url, row.cpyrht_div_cd),
        lat=row.mapy,
        lng=row.mapx,
    )


async def answer_about_spot(
    session: AsyncSession,
    redis: Redis,
    kto: KtoClient | None,
    *,
    content_id: str,
    intent: QueryIntent,
    steps: list[AskStep],
) -> AskResponse:
    try:
        row = await load_spot_detail(
            session,
            kto,  # type: ignore[arg-type]
            redis,
            content_id,
            defer_refresh=kto is None,
        )
    except AppError as exc:
        logger.warning("agent.detail.unavailable", code=exc.code)
        raise AgentNoResults() from exc

    fields = _asked(intent)
    answer: list[AnswerSegment] = [AnswerSegment(text=f"{row.title} ")]
    if row.detail_status in ("pending", "unavailable"):
        answer.append(AnswerSegment(text=f"{STALE_HINT}. 상세 화면에서 다시 확인해 주세요."))
    else:
        for index, field in enumerate(fields):
            if index:
                answer.append(AnswerSegment(text=" "))
            answer.extend(_sentence(row, field))
    steps = [*steps, AskStep(tool="spot_detail", label=f"{row.title} 상세 조회", badge="KTO")]
    logger.info(
        "agent.detail.done",
        fields=len(fields),
        status=row.detail_status,
        answered=sum(1 for f in fields if field_value(row.intro, row.tel, f)),
    )
    return AskResponse(
        steps=steps,
        answer=answer,
        spots=[_card(row)],
        totalCount=1,
        intent=intent,
        refinements=[],
    )
