from __future__ import annotations

from app.core.db import AsyncSession
from app.core.logging import get_logger
from app.modules.agent import repositories
from app.modules.agent.emitter import begin_step
from app.modules.agent.kakao_places import PlaceKind
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
    ResolvedPlace,
)
from app.modules.agent.services import geocode as geocode_service
from app.modules.agent.services import places as places_service
from app.modules.agent.services import retrieve
from app.modules.agent.services.anchor import (
    ANCHOR_CATEGORIES,
    ANCHOR_NOUNS,
    ANCHOR_RADIUS_M,
    anchor_card,
    anchor_lead,
    ask_with_anchor,
    empty_anchor_response,
    fill_missing_card_images,
    has_crowd,
    locatable_focus,
)
from app.modules.agent.services.answer import (
    PLACES_BASIS,
    card,
    talk_response,
    without_unapplied_axes,
)
from app.modules.agent.services.branches import count
from app.modules.agent.services.phrasing import (
    dish_title_condition,
    km_label,
    subject_particle,
)
from app.modules.spots.services import find_nearby_spots

logger = get_logger(__name__)

FOOD_NEEDS_ORIGIN_ANSWER = (
    "맛집·카페는 장소를 하나 골라 주시면 그 주변으로 찾아드려요. "
    "카드를 한 번 탭하거나 위치를 켜 주세요."
)
KAKAO_TOPUP_LABEL = "카카오맵에서 보충"
THIN_KTO_POOL = 10
CROWD_LABELS: dict[str, str] = {"quiet": "한적한 곳", "popular": "유명한 곳"}


def dropped_labels(intent: QueryIntent) -> list[str]:
    """좁힌 조건으로 0곳이라 풀어버린 축을 사용자 말로 옮긴다."""
    labels: list[str] = []
    if (crowd := CROWD_LABELS.get(intent.crowdPreference)) is not None:
        labels.append(crowd)
    if intent.indoorOnly:
        labels.append("실내")
    if intent.moodHints:
        labels.append("분위기")
    return labels


VERIFIED_ORIGIN_STATUSES = ("matched", "naver_only")


def _verified_origin(place: ResolvedPlace) -> geocode_service.Located | None:
    spot = place.spot
    if spot is None or spot.lat is None or spot.lng is None:
        return None
    if place.status not in VERIFIED_ORIGIN_STATUSES:
        return None
    asked = [name for name in (place.extracted.nameKo, place.extracted.name) if name]
    if not any(geocode_service.names_match(name, spot.title) for name in asked):
        return None
    terms = geocode_service.region_terms(place.extracted.regionHint)
    if not geocode_service.address_is_within(spot.address, terms):
        return None
    return geocode_service.Located(
        title=spot.title,
        lat=spot.lat,
        lng=spot.lng,
        source=spot.source,
        content_id=spot.contentId,
    )


def _stands_in_region(row: CandidateRow, prefixes: list[str]) -> bool:
    if not prefixes:
        return True
    return row.addr1 is not None and row.addr1.startswith(tuple(prefixes))


async def _named_origin(
    session: AsyncSession, intent: QueryIntent, resolved: list[ResolvedPlace]
) -> geocode_service.Located | None:
    for index, place in enumerate(intent.namedPlaces):
        reused = _verified_origin(resolved[index]) if index < len(resolved) else None
        if reused is not None:
            return reused
        found = await geocode_service.locate(session, place.name, region_hint=place.regionHint)
        if found is not None:
            return found
    return None


async def ask_for_food(
    session: AsyncSession,
    *,
    action: AnchorAction,
    intent: QueryIntent,
    steps: list[AskStep],
    lat: float | None,
    lng: float | None,
    context: AskContext | None,
    resolved: list[ResolvedPlace],
    title_terms: list[str],
) -> AskResponse:
    scope = await retrieve.resolve_region_scope(session, hints=intent.regionHints)
    stale = context is not None and named_a_new_region(intent, context)
    focus = None if stale else await locatable_focus(session, context)
    if focus is not None and _stands_in_region(focus, scope.prefixes):
        return await ask_with_anchor(
            session,
            AskAnchor(contentId=focus.content_id, action=action),
            lat=lat,
            lng=lng,
            prior_steps=steps,
            carried_intent=intent,
            title_terms=title_terms,
        )
    origin = await _named_origin(session, intent, resolved)
    if origin is not None:
        located = [
            *steps,
            AskStep(tool="resolve_place", label=f"{origin.title} 위치 확인", badge="1곳"),
        ]
        return await _ask_around(
            session,
            origin.title,
            action,
            lat=origin.lat,
            lng=origin.lng,
            steps=located,
            intent=intent,
            exclude=origin.content_id,
            title_terms=title_terms,
        )
    if scope.prefixes:
        return await _food_across_region(
            session,
            action,
            scope.prefixes,
            steps=steps,
            intent=intent,
            lat=lat,
            lng=lng,
            title_terms=title_terms,
        )
    if lat is not None and lng is not None:
        return await ask_with_anchor(
            session,
            AskAnchor(action=action),
            lat=lat,
            lng=lng,
            prior_steps=steps,
            carried_intent=intent,
            title_terms=title_terms,
        )
    return talk_response(steps, intent, FOOD_NEEDS_ORIGIN_ANSWER)


async def _food_across_region(
    session: AsyncSession,
    action: AnchorAction,
    prefixes: list[str],
    *,
    steps: list[AskStep],
    intent: QueryIntent,
    lat: float | None,
    lng: float | None,
    title_terms: list[str] | None = None,
) -> AskResponse:
    near = intent.nearMe and lat is not None and lng is not None
    spoken = intent if near or not intent.nearMe else intent.model_copy(update={"nearMe": False})
    mood_ids = await repositories.find_mood_ids(session, list(intent.moodHints))
    narrowed = bool(mood_ids) or intent.indoorOnly or intent.crowdPreference != "any"
    rows = await retrieve.search_food(
        session,
        action=action,
        region_prefixes=prefixes,
        preference=intent.crowdPreference,
        indoor_only=intent.indoorOnly,
        mood_ids=mood_ids,
        lat=lat,
        lng=lng,
        near=near,
        title_terms=title_terms,
    )
    if len(rows) < THIN_KTO_POOL:
        topped = await _top_up_with_kakao(
            session,
            action,
            prefixes,
            rows=rows,
            steps=steps,
            intent=spoken,
            lat=lat,
            lng=lng,
            near=near,
            title_terms=title_terms,
        )
        if topped is not None:
            return topped
    if rows or not narrowed:
        return food_in_region(
            rows,
            prefixes,
            action,
            steps=steps,
            intent=spoken,
            lat=lat,
            lng=lng,
            near=near,
            title_terms=title_terms,
        )
    unfiltered = await retrieve.search_food(
        session,
        action=action,
        region_prefixes=prefixes,
        lat=lat,
        lng=lng,
        near=near,
        title_terms=title_terms,
    )
    return food_in_region(
        unfiltered,
        prefixes,
        action,
        steps=steps,
        intent=without_unapplied_axes(spoken),
        unmet=dropped_labels(spoken),
        lat=lat,
        lng=lng,
        near=near,
        title_terms=title_terms,
    )


async def _top_up_with_kakao(
    session: AsyncSession,
    action: AnchorAction,
    prefixes: list[str],
    *,
    rows: list[CandidateRow],
    steps: list[AskStep],
    intent: QueryIntent,
    lat: float | None,
    lng: float | None,
    near: bool,
    title_terms: list[str] | None,
) -> AskResponse | None:
    """생활권에서는 KTO 음식·카페가 사실상 비어 있다 (광진구 카페 1곳).

    관광지형은 두꺼우므로 카테고리가 아니라 후보 수로 갈린다.
    """
    kind: PlaceKind = "cafe" if action == "cafe" else "restaurant"
    coords = (lat, lng) if near and lat is not None and lng is not None else None
    begin_step(steps, "nearby", KAKAO_TOPUP_LABEL)
    cards = await places_service.search(
        session,
        kind=kind,
        region=prefixes[0] if prefixes else None,
        landmark_coords=coords,
        dish=title_terms[0] if title_terms else None,
        attribute=None,
    )
    if not cards:
        return None
    steps.append(AskStep(tool="nearby", label=KAKAO_TOPUP_LABEL, badge=f"{len(cards)}곳"))
    kept = [card(row, intent=intent, lat=lat, lng=lng, near=near) for row in rows]
    known = {card.contentId for card in kept}
    merged = kept + [card for card in cards if card.contentId not in known]
    return AskResponse(
        steps=steps,
        answer=_places_answer(merged),
        spots=merged,
        totalCount=len(merged),
        intent=intent,
        refinements=[],
        tagBasis=PLACES_BASIS,
    )


def _places_answer(cards: list[AgentSpotCard]) -> list[AnswerSegment]:
    reduced = sum(1 for card in cards if not card.saveable)
    lead = f"{len(cards)}곳이에요."
    if not reduced:
        return [AnswerSegment(text=lead)]
    return [
        AnswerSegment(text=f"{lead} 블로그에 반복해서 나온 순으로 놨어요."),
        AnswerSegment(
            text=f" 이 중 {reduced}곳은 저희 여행지 정보에 없어 저장·상세보기가 안 돼요."
        ),
    ]


async def _ask_around(
    session: AsyncSession,
    origin: str,
    action: AnchorAction,
    *,
    lat: float,
    lng: float,
    steps: list[AskStep],
    intent: QueryIntent,
    exclude: str | None = None,
    title_terms: list[str] | None = None,
) -> AskResponse:
    noun = ANCHOR_NOUNS[action]
    found = await find_nearby_spots(
        session,
        lat=lat,
        lng=lng,
        radius=ANCHOR_RADIUS_M,
        category=ANCHOR_CATEGORIES[action],
        title_terms=title_terms,
    )
    kept = [near for near in found if near.content_id != exclude][: retrieve.RESULT_LIMIT]
    if not kept:
        return empty_anchor_response(
            origin,
            action,
            prior_steps=steps,
            intent=intent,
            title_terms=title_terms,
        )
    rated = await repositories.load_candidates_by_ids(session, [n.content_id for n in kept])
    spots = [anchor_card(near, has_crowd=has_crowd(rated.get(near.content_id))) for near in kept]
    await fill_missing_card_images(session, spots)
    walked = [
        *steps,
        AskStep(tool="nearby", label=f"{origin} 주변 {noun} 조회", badge=f"{len(kept)}곳"),
    ]
    answer = [
        *anchor_lead(origin, action, nearest_m=kept[0].dist),
        AnswerSegment(text=f" {origin} 주변으로 "),
        AnswerSegment(text=f"{len(spots)}곳이에요."),
    ]
    logger.info("agent.food.around", action=action, results=len(spots))
    return AskResponse(
        steps=walked,
        answer=answer,
        spots=spots,
        totalCount=len(spots),
        intent=without_unapplied_axes(intent),
        tagBasis="직선거리 기준",
        refinements=[],
    )


def food_in_region(
    rows: list[CandidateRow],
    regions: list[str],
    action: AnchorAction,
    *,
    steps: list[AskStep],
    intent: QueryIntent,
    lat: float | None = None,
    lng: float | None = None,
    near: bool = False,
    title_terms: list[str] | None = None,
    unmet: list[str] | None = None,
) -> AskResponse:
    noun = ANCHOR_NOUNS[action]
    where = " · ".join(regions)
    top = rows[: retrieve.RESULT_LIMIT]
    scanned = [
        *steps,
        AskStep(tool="category_search", label=f"{where} {noun} 조회", badge=count(rows)),
    ]
    if not top:
        answer = (
            [
                AnswerSegment(
                    text=f"{where}에서 {dish_title_condition(title_terms)}을 찾지 못했어요."
                )
            ]
            if title_terms
            else [AnswerSegment(text=f"{where}에는 등록된 {noun}{subject_particle(noun)} 없어요.")]
        )
        return AskResponse(
            steps=scanned,
            answer=answer,
            spots=[],
            totalCount=0,
            intent=intent,
            refinements=[],
        )
    spots = [_region_food_card(row, lat=lat, lng=lng, near=near) for row in top]
    logger.info("agent.food.region", action=action, results=len(spots), unmet=len(unmet or []))
    lead = (
        [AnswerSegment(text=f"{' · '.join(unmet)} 조건으로는 없어서 그 조건을 빼고 찾았어요. ")]
        if unmet
        else []
    )
    return AskResponse(
        steps=scanned,
        answer=[
            *lead,
            AnswerSegment(text=where, emphasis=True),
            AnswerSegment(text=f" {noun} "),
            AnswerSegment(text=f"{len(spots)}곳이에요."),
        ],
        unmet=list(unmet or []),
        spots=spots,
        totalCount=len(spots),
        intent=intent,
        tagBasis="직선거리 기준" if near else None,
        refinements=[],
    )


def _region_food_card(
    row: CandidateRow, *, lat: float | None, lng: float | None, near: bool
) -> AgentSpotCard:
    if near and lat is not None and lng is not None:
        km = retrieve.distance_km(row, lat=lat, lng=lng)
        if km is not None:
            return retrieve.to_card(row, tag=km_label(km))
    return retrieve.to_card(row, tag=None)


def named_a_new_region(intent: QueryIntent, context: AskContext) -> bool:
    carried = list(context.intent.regionHints) if context.intent else []
    return bool(intent.regionHints) and list(intent.regionHints) != carried
