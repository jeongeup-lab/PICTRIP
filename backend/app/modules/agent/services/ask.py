from __future__ import annotations

from app.core.db import AsyncSession
from app.core.logging import get_logger
from app.kto.client import KtoClient
from app.modules.agent import repositories
from app.modules.agent.errors import AgentNoResults
from app.modules.agent.repositories import CandidateRow
from app.modules.agent.schemas import (
    AgentSpotCard,
    AnswerSegment,
    AskFilters,
    AskResponse,
    AskStep,
    QueryIntent,
)
from app.modules.agent.services import intent as intent_service
from app.modules.agent.services import photo as photo_service
from app.modules.agent.services import resolve as resolve_service
from app.modules.agent.services import retrieve
from app.web.errors import ValidationFailed

logger = get_logger(__name__)

WHEN_LABELS = {
    "any": None,
    "today": "오늘",
    "weekend": "이번 주말",
    "next_week": "다음 주",
}

BASE_SUGGESTIONS = ["더 한적한 곳", "실내 위주", "더 가까운 곳"]
NEAR_SUGGESTIONS = ["더 비슷하게", "더 가까운 곳", "실내 위주"]


async def ask(
    session: AsyncSession,
    kto: KtoClient | None,
    *,
    question: str | None,
    filters: AskFilters,
    lat: float | None,
    lng: float | None,
    image_bytes: bytes | None,
    image_mime: str | None,
) -> AskResponse:
    if image_bytes:
        return await _ask_with_photo(
            session, image_bytes=image_bytes, image_mime=image_mime, filters=filters
        )
    if not question or not question.strip():
        raise ValidationFailed("question or photo is required")
    return await _ask_with_question(
        session, kto, question=question.strip(), filters=filters, lat=lat, lng=lng
    )


async def _ask_with_photo(
    session: AsyncSession,
    *,
    image_bytes: bytes,
    image_mime: str | None,
    filters: AskFilters,
) -> AskResponse:
    steps: list[AskStep] = []
    rows = await photo_service.match_photo(session, image_bytes=image_bytes, image_mime=image_mime)
    steps.append(
        AskStep(tool="photo_match", label="사진을 CLIP으로 임베딩해 벡터 비교", badge="pgvector")
    )

    similarity = {row.content_id: photo_service.similarity(row) for row in rows}
    briefs = await repositories.load_candidates_by_ids(session, [row.content_id for row in rows])
    ordered = [briefs[row.content_id] for row in rows if row.content_id in briefs]
    ordered = _apply_region(ordered, filters)
    steps.append(AskStep(tool="concentration", label="지역 조건 확인", badge=_count(ordered)))

    if not ordered:
        raise AgentNoResults()

    top = ordered[: retrieve.RESULT_LIMIT]
    spots = [
        retrieve.to_card(row, tag=f"유사도 {round(similarity.get(row.content_id, 0.0) * 100)}%")
        for row in top
    ]
    answer = [
        AnswerSegment(text="사진과 닮은 곳으로 "),
        AnswerSegment(text=f"{len(top)}곳", emphasis=True),
        AnswerSegment(text=" 찾았어요. 원본 사진은 비교 후 바로 폐기했어요."),
    ]
    return AskResponse(
        steps=steps,
        answer=answer,
        spots=spots,
        totalCount=len(ordered),
        suggestions=NEAR_SUGGESTIONS,
    )


async def _ask_with_question(
    session: AsyncSession,
    kto: KtoClient | None,
    *,
    question: str,
    filters: AskFilters,
    lat: float | None,
    lng: float | None,
) -> AskResponse:
    steps: list[AskStep] = []
    intent = await intent_service.extract_intent(question)
    steps.append(AskStep(tool="intent", label="질문에서 지역·조건 추출", badge="Gemini"))

    pinned: list[CandidateRow] = []
    if intent.namedPlaces:
        resolved = await resolve_service.resolve_places(session, kto, intent.namedPlaces)
        content_ids = [
            place.spot.contentId
            for place in resolved
            if place.spot is not None and place.spot.contentId
        ]
        briefs = await repositories.load_candidates_by_ids(session, content_ids)
        pinned = [briefs[cid] for cid in content_ids if cid in briefs]
        steps.append(AskStep(tool="resolve_place", label="질문 속 장소 확인", badge=_count(pinned)))

    keywords = _keywords(intent, filters)
    codes = await retrieve.resolve_category_codes(session, keywords)
    candidates = await retrieve.search_candidates(session, codes=codes, region=filters.region)
    steps.append(
        AskStep(
            tool="category_search",
            label=_search_label(keywords, filters),
            badge=_count(candidates),
        )
    )

    pool = candidates
    if intent.crowdPreference != "any":
        pool = retrieve.filter_by_crowd(pool, intent.crowdPreference)
        steps.append(AskStep(tool="concentration", label="혼잡도로 추림", badge=_count(pool)))

    if intent.nearMe and lat is not None and lng is not None:
        pool = retrieve.sort_by_distance(pool, lat=lat, lng=lng)
        steps.append(AskStep(tool="nearby", label="현재 위치에서 가까운 순", badge=_count(pool)))

    merged = _merge(pinned, pool)
    if not merged:
        raise AgentNoResults()

    top = merged[: retrieve.RESULT_LIMIT]
    near = intent.nearMe and lat is not None and lng is not None
    spots = [_card(row, pool=merged, intent=intent, lat=lat, lng=lng, near=near) for row in top]
    logger.info(
        "agent.ask.done",
        candidates=len(candidates),
        pool=len(pool),
        results=len(top),
        crowd=intent.crowdPreference,
    )
    return AskResponse(
        steps=steps,
        answer=_answer(top, merged, intent=intent, filters=filters, near=near, lat=lat, lng=lng),
        spots=spots,
        totalCount=len(merged),
        suggestions=BASE_SUGGESTIONS,
    )


def _keywords(intent: QueryIntent, filters: AskFilters) -> list[str]:
    keywords = list(intent.categoryKeywords)
    extra = retrieve.INDOOR_KEYWORDS if intent.indoorOnly else ()
    for keyword in (*extra, *retrieve.WHO_KEYWORDS[filters.who]):
        if keyword not in keywords:
            keywords.append(keyword)
    return keywords


def _search_label(keywords: list[str], filters: AskFilters) -> str:
    head = " · ".join(keywords[:2]) if keywords else retrieve.REGION_LABELS[filters.region]
    return f"{head} 관광지 조회"


def _apply_region(rows: list[CandidateRow], filters: AskFilters) -> list[CandidateRow]:
    prefixes = retrieve.REGION_PREFIXES[filters.region]
    if not prefixes:
        return rows
    return [row for row in rows if row.addr1 and row.addr1.startswith(prefixes)]


def _merge(pinned: list[CandidateRow], pool: list[CandidateRow]) -> list[CandidateRow]:
    seen = {row.content_id for row in pinned}
    return pinned + [row for row in pool if row.content_id not in seen]


def _card(
    row: CandidateRow,
    *,
    pool: list[CandidateRow],
    intent: QueryIntent,
    lat: float | None,
    lng: float | None,
    near: bool,
) -> AgentSpotCard:
    if near and lat is not None and lng is not None:
        km = retrieve.distance_km(row, lat=lat, lng=lng)
        if km is not None:
            return retrieve.to_card(row, tag=f"{km:.1f}km")
    if intent.crowdPreference == "quiet":
        pct = retrieve.percentile(row, pool)
        if pct is not None:
            return retrieve.to_card(row, tag=f"하위 {pct}%")
    return retrieve.to_card(row, tag=retrieve.crowd_label(row))


def _answer(
    top: list[CandidateRow],
    pool: list[CandidateRow],
    *,
    intent: QueryIntent,
    filters: AskFilters,
    near: bool,
    lat: float | None,
    lng: float | None,
) -> list[AnswerSegment]:
    segments = [AnswerSegment(text="조건에 맞는 곳으로 ")]
    segments.append(AnswerSegment(text=f"{len(top)}곳", emphasis=True))
    segments.append(AnswerSegment(text=" 추렸어요"))

    when_label = WHEN_LABELS[filters.when]
    if when_label:
        segments.append(AnswerSegment(text=f" ({when_label} 기준)"))

    if intent.crowdPreference == "quiet":
        pcts = [p for row in top if (p := retrieve.percentile(row, pool)) is not None]
        if pcts:
            segments.append(AnswerSegment(text=". 모두 이 조건 안에서 혼잡도 "))
            segments.append(AnswerSegment(text=f"하위 {max(pcts)}%", emphasis=True))
            segments.append(AnswerSegment(text=" 안쪽이에요."))
            return segments
    if near and lat is not None and lng is not None:
        kms = [km for row in top if (km := retrieve.distance_km(row, lat=lat, lng=lng))]
        if kms:
            segments.append(AnswerSegment(text=". 가장 가까운 곳은 "))
            segments.append(AnswerSegment(text=f"{min(kms):.1f}km", emphasis=True))
            segments.append(AnswerSegment(text=" 거리예요."))
            return segments
    segments.append(AnswerSegment(text=". 마음에 드는 게 없으면 조건을 좁혀 말해주세요."))
    return segments


def _count(rows: list[CandidateRow]) -> str:
    return f"{len(rows)}곳"
