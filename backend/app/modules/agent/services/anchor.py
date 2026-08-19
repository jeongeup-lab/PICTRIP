from __future__ import annotations

from app.core.db import AsyncSession
from app.core.logging import get_logger
from app.kto.display import T1_TILE_WIDTH, t1_display_url
from app.modules.agent import repositories
from app.modules.agent.emitter import Emitter, branch_of
from app.modules.agent.errors import AgentNoResults
from app.modules.agent.repositories import CandidateRow
from app.modules.agent.schemas import (
    AgentSpotCard,
    AnchorAction,
    AnswerSegment,
    AskAnchor,
    AskContext,
    AskResponse,
    AskStep,
    QueryIntent,
)
from app.modules.agent.services import detail as detail_service
from app.modules.agent.services import photo as photo_service
from app.modules.agent.services import retrieve
from app.modules.agent.services.answer import (
    RELATED_BASIS,
    without_unapplied_axes,
)
from app.modules.agent.services.phrasing import (
    addr_label,
    copula,
    dish_title_condition,
    meters_label,
    subject_particle,
)
from app.modules.spots.categories import NearbyCategory
from app.modules.spots.services import NearbySpotRow, find_nearby_spots
from app.web.errors import ValidationFailed

logger = get_logger(__name__)

ANCHOR_RADIUS_M = 3000
ANCHOR_CATEGORIES: dict[str, NearbyCategory] = {
    "food": NearbyCategory.food,
    "cafe": NearbyCategory.cafe,
    "nearby": NearbyCategory.attraction,
}
ANCHOR_NOUNS: dict[str, str] = {"food": "맛집", "cafe": "카페", "nearby": "볼거리"}


async def ask_with_anchor(
    session: AsyncSession,
    anchor: AskAnchor,
    *,
    lat: float | None,
    lng: float | None,
    prior_steps: list[AskStep] | None = None,
    carried_intent: QueryIntent | None = None,
    title_terms: list[str] | None = None,
    emitter: Emitter | None = None,
) -> AskResponse:
    row: CandidateRow | None = None
    if anchor.contentId is not None:
        briefs = await repositories.load_candidates_by_ids(session, [anchor.contentId])
        row = briefs.get(anchor.contentId)
        if row is None:
            raise AgentNoResults()
    if anchor.action == "crowd":
        if row is None:
            raise ValidationFailed("crowd anchor requires contentId")
        return _anchor_crowd_response(row)
    if anchor.action == "related":
        if row is None:
            raise ValidationFailed("related anchor requires contentId")
        return await _anchor_related_response(
            session, row, prior_steps=prior_steps or [], carried_intent=carried_intent
        )
    center_lat = row.lat if row is not None else lat
    center_lng = row.lng if row is not None else lng
    if center_lat is None or center_lng is None:
        if row is None:
            raise ValidationFailed("anchor requires contentId or coords")
        raise AgentNoResults()
    origin = row.title if row is not None else "내 위치"
    noun = ANCHOR_NOUNS[anchor.action]
    found = await find_nearby_spots(
        session,
        lat=center_lat,
        lng=center_lng,
        radius=ANCHOR_RADIUS_M,
        category=ANCHOR_CATEGORIES[anchor.action],
        travel_only=anchor.action == "nearby",
        title_terms=title_terms,
    )
    kept = [near for near in found if row is None or near.content_id != row.content_id]
    kept = kept[: retrieve.RESULT_LIMIT]
    if not kept:
        return empty_anchor_response(
            origin,
            anchor.action,
            prior_steps=prior_steps or [],
            intent=carried_intent,
            title_terms=title_terms,
        )
    rated = await repositories.load_candidates_by_ids(session, [n.content_id for n in kept])
    spots = [anchor_card(near, has_crowd=has_crowd(rated.get(near.content_id))) for near in kept]
    await fill_missing_card_images(session, spots)
    steps = branch_of(prior_steps or [], prior_steps or [])
    if steps.emitter is None:
        steps.emitter = emitter
    steps.append(
        AskStep(tool="nearby", label=f"{origin} 주변 {noun} 조회", badge=f"{len(spots)}곳")
    )
    answer = [
        *anchor_lead(origin, anchor.action, nearest_m=kept[0].dist),
        AnswerSegment(text=f" {origin} 주변으로 "),
        AnswerSegment(text=f"{len(spots)}곳이에요."),
    ]
    logger.info("agent.anchor.done", action=anchor.action, results=len(spots))
    return AskResponse(
        steps=steps,
        answer=answer,
        spots=spots,
        totalCount=len(spots),
        intent=without_unapplied_axes(carried_intent or QueryIntent()),
        tagBasis="직선거리 기준",
        refinements=[],
    )


def empty_anchor_response(
    origin: str,
    action: AnchorAction,
    *,
    prior_steps: list[AskStep],
    intent: QueryIntent | None = None,
    title_terms: list[str] | None = None,
) -> AskResponse:
    noun = ANCHOR_NOUNS[action]
    steps = [
        *prior_steps,
        AskStep(tool="nearby", label=f"{origin} 주변 {noun} 조회", badge="0곳"),
    ]
    logger.info("agent.anchor.empty", action=action)
    answer = (
        [
            AnswerSegment(
                text=(
                    f"{origin} 주변 {ANCHOR_RADIUS_M // 1000}km 안에서 "
                    f"{dish_title_condition(title_terms)}을 찾지 못했어요. "
                    "다른 곳을 골라 보세요."
                )
            )
        ]
        if title_terms
        else [
            AnswerSegment(text=f"{origin} 주변 "),
            AnswerSegment(text=f"{ANCHOR_RADIUS_M // 1000}km", emphasis=True),
            AnswerSegment(
                text=f" 안에는 {noun}{subject_particle(noun)} 없어요. 다른 곳을 골라 보세요."
            ),
        ]
    )
    return AskResponse(
        steps=steps,
        answer=answer,
        spots=[],
        totalCount=0,
        intent=without_unapplied_axes(intent or QueryIntent()),
        refinements=[],
    )


def anchor_lead(
    origin: str, action: AnchorAction, *, nearest_m: float | None
) -> list[AnswerSegment]:
    noun = ANCHOR_NOUNS[action]
    if nearest_m is None:
        return [AnswerSegment(text=f"{origin} 주변 {noun}{copula(noun)}.")]
    return [
        AnswerSegment(text=f"가장 가까운 {noun}{subject_particle(noun)} "),
        AnswerSegment(text=meters_label(nearest_m), emphasis=True),
        AnswerSegment(text=" 거리예요."),
    ]


async def _anchor_related_response(
    session: AsyncSession,
    row: CandidateRow,
    *,
    prior_steps: list[AskStep],
    carried_intent: QueryIntent | None,
) -> AskResponse:
    vector = await repositories.load_spot_embedding(session, row.content_id)
    if vector is None:
        raise AgentNoResults()
    matches = await repositories.match_spots_by_vector(
        session, vector, limit=retrieve.RESULT_LIMIT + 1
    )
    kept = [match for match in matches if match.content_id != row.content_id]
    kept = kept[: retrieve.RESULT_LIMIT]
    briefs = await repositories.load_candidates_by_ids(
        session, [match.content_id for match in kept]
    )
    spots = [
        retrieve.to_card(
            briefs[match.content_id],
            tag=f"유사도 {round(photo_service.similarity(match) * 100)}%",
        )
        for match in kept
        if match.content_id in briefs
    ]
    if not spots:
        raise AgentNoResults()
    steps = [
        *prior_steps,
        AskStep(tool="related", label=f"{row.title} 연관 관광지 조회", badge=f"{len(spots)}곳"),
    ]
    particle = "과" if detail_service.ends_with_consonant(row.title) else "와"
    answer = [
        AnswerSegment(text=f"「{row.title}」", emphasis=True),
        AnswerSegment(text=f"{particle} 분위기가 비슷한 곳으로 "),
        AnswerSegment(text=f"{len(spots)}곳 찾았어요."),
    ]
    logger.info("agent.anchor.done", action="related", results=len(spots))
    return AskResponse(
        steps=steps,
        answer=answer,
        spots=spots,
        totalCount=len(spots),
        intent=without_unapplied_axes(carried_intent or QueryIntent()),
        tagBasis=RELATED_BASIS,
        refinements=[],
    )


def _anchor_crowd_response(row: CandidateRow) -> AskResponse:
    steps = [AskStep(tool="concentration", label=f"{row.title} 혼잡도 조회", badge="혼잡도")]
    label = retrieve.crowd_label(row)
    if label is None:
        answer = [AnswerSegment(text=f"{row.title}의 혼잡도 정보가 아직 없어요.")]
    else:
        answer = [
            AnswerSegment(text=f"{row.title} 오늘 혼잡도 예측은 "),
            AnswerSegment(text=label, emphasis=True),
            AnswerSegment(text=" 수준이에요."),
        ]
        if label == "한산" and row.percentile is not None:
            answer.append(AnswerSegment(text=" 전국 관광지 중 "))
            answer.append(AnswerSegment(text=f"하위 {row.percentile}%", emphasis=True))
            answer.append(AnswerSegment(text=" 안쪽이에요."))
        elif label == "붐빔" and row.percentile is not None:
            answer.append(AnswerSegment(text=" 전국 관광지 중 "))
            answer.append(AnswerSegment(text=f"상위 {100 - row.percentile}%", emphasis=True))
            answer.append(AnswerSegment(text=" 안쪽이에요."))
    logger.info("agent.anchor.done", action="crowd", results=0)
    return AskResponse(
        steps=steps,
        answer=answer,
        spots=[],
        totalCount=0,
        intent=QueryIntent(),
        refinements=[],
    )


def has_crowd(row: CandidateRow | None) -> bool:
    return row is not None and row.concentration_rate is not None


async def fill_missing_card_images(session: AsyncSession, spots: list[AgentSpotCard]) -> None:
    missing = [card for card in spots if not card.imageUrl]
    if not missing:
        return
    pool = await repositories.load_random_attraction_images(session, len(missing))
    urls = [
        url
        for url in (t1_display_url(r.image_url, r.cpyrht_div_cd, width=T1_TILE_WIDTH) for r in pool)
        if url
    ]
    for card, url in zip(missing, urls, strict=False):
        card.imageUrl = None
        card.fallbackImageUrl = url


def anchor_card(row: NearbySpotRow, *, has_crowd: bool) -> AgentSpotCard:
    return AgentSpotCard(
        contentId=row.content_id,
        title=row.title,
        regionLabel=addr_label(row.addr1),
        imageUrl=t1_display_url(row.first_image_url, row.cpyrht_div_cd),
        tag=meters_label(row.dist) if row.dist is not None else None,
        lat=row.mapy,
        lng=row.mapx,
        categoryGroup=row.category_group,
        hasCrowd=has_crowd,
    )


async def locatable_focus(session: AsyncSession, context: AskContext | None) -> CandidateRow | None:
    if context is None or context.focusContentId is None:
        return None
    briefs = await repositories.load_candidates_by_ids(session, [context.focusContentId])
    row = briefs.get(context.focusContentId)
    if row is None or row.lat is None or row.lng is None:
        return None
    return row
