from __future__ import annotations

import asyncio
import re

from redis.asyncio import Redis

from app.core.db import AsyncSession
from app.core.logging import get_logger
from app.kto.client import KtoClient
from app.kto.display import t1_display_url
from app.modules.agent import repositories
from app.modules.agent.emitter import Emitter, Steps, begin_step
from app.modules.agent.errors import (
    AgentFestivalUnavailable,
    AgentNoResults,
    AgentOutOfScope,
)
from app.modules.agent.repositories import CandidateRow
from app.modules.agent.schemas import (
    MAX_HINT_TOKENS,
    MAX_KEYWORDS,
    AgentSpotCard,
    AnchorAction,
    AnswerSegment,
    AskAnchor,
    AskContext,
    AskResponse,
    AskStep,
    QueryIntent,
    RefinePatch,
    ResolvedPlace,
)
from app.modules.agent.services import detail as detail_service
from app.modules.agent.services import intent as intent_service
from app.modules.agent.services import refine as refine_service
from app.modules.agent.services import region as region_service
from app.modules.agent.services import resolve as resolve_service
from app.modules.agent.services import retrieve, routes
from app.modules.agent.services import scene as scene_service
from app.modules.agent.services import suggest as suggest_service
from app.modules.agent.services.anchor import (
    _ask_with_anchor,
    _subject_particle,
)
from app.modules.agent.services.answer import (
    _answer,
    _card,
    _fallback_sentence,
    _keep,
    _merge,
    _tag_basis,
    _talk_response,
    _zero_response,
    searched_intent,
)
from app.modules.agent.services.food import (
    _ask_for_food,
    _named_a_new_region,
)
from app.modules.agent.services.photo_ask import (
    _ask_with_photo,
)
from app.modules.agent.services.routes import count
from app.modules.feed import services as feed_services
from app.modules.spots.services import (
    load_active_spot_cards_by_ids,
)
from app.web.errors import AppError, ValidationFailed

logger = get_logger(__name__)

BLANK_ANSWER = "어디로 갈지 한 줄만 알려주세요. 지역 · 분위기 · 사진 아무거나 좋아요."
NO_AXIS_ANSWER = "어느 지역으로 찾아볼까요? 지역이나 분위기를 알려주시면 바로 찾아드릴게요."
UNSUPPORTED_ANSWER = (
    "그건 아직 못 해요. 지역·분위기로 여행지를 찾거나, "
    "카드를 골라 이용시간·주차 같은 걸 물어봐 주세요."
)
CONTEXT_INTENT_LABEL = "앞 대화까지 보고 조건 추출"
INTENT_FALLBACK_BADGE = "사전 매칭"
INTENT_MODEL_BADGE = "AI 해석"
GUESSED_REGION_LABEL = "현재 위치로 지역 추정"
SUB_QUESTION_CARDS = 6
NEAR_PROBE_LABEL = "근처 조건 없이 다시 재보기"
FESTIVAL_FETCH_BUDGET_SECONDS = 4.0
METERS_STEP = 10
DISTANCE_TAG = re.compile(r"^\d+(\.\d+)?(km|m)$")
ORIGIN_ACTION_WORDS: tuple[tuple[str, AnchorAction], ...] = (
    ("카페", "cafe"),
    ("커피", "cafe"),
    ("맛집", "food"),
    ("음식", "food"),
    ("식당", "food"),
    ("먹을", "food"),
)
MIN_HINT_TOKEN_CHARS = 2
SIDO_ALIASES: dict[str, tuple[str, ...]] = {
    "강원도": ("강원",),
    "경남": ("경상남도",),
    "경북": ("경상북도",),
    "경상남도": ("경남",),
    "경상북도": ("경북",),
    "전남": ("전라남도",),
    "전라남도": ("전남",),
    "전라북도": ("전북",),
    "전북": ("전라북도",),
    "제주도": ("제주",),
    "충남": ("충청남도",),
    "충북": ("충청북도",),
    "충청남도": ("충남",),
    "충청북도": ("충북",),
}


async def ask(
    session: AsyncSession,
    redis: Redis,
    kto: KtoClient | None,
    *,
    question: str | None,
    lat: float | None,
    lng: float | None,
    image_bytes: bytes | None,
    image_mime: str | None,
    intent: QueryIntent | None = None,
    patch: RefinePatch | None = None,
    anchor: AskAnchor | None = None,
    context: AskContext | None = None,
    pre_ota_region_prefixes: list[str] | None = None,
    legacy_client: bool = False,
    emitter: Emitter | None = None,
) -> AskResponse:
    cleaned = (question or "").strip()
    if anchor is not None:
        if image_bytes is not None:
            raise ValidationFailed("anchor cannot be combined with photo")
        return await _ask_with_anchor(session, anchor, lat=lat, lng=lng, emitter=emitter)
    if image_bytes is not None:
        return await _ask_with_photo(
            session,
            question=cleaned,
            image_bytes=image_bytes,
            image_mime=image_mime,
            lat=lat,
            lng=lng,
            intent=intent,
            patch=patch,
            pre_ota_region_prefixes=pre_ota_region_prefixes or [],
            legacy_client=legacy_client,
            emitter=emitter,
        )
    if not cleaned and intent is None:
        raise ValidationFailed("question, photo or intent is required")
    return await _ask_with_question(
        session,
        redis,
        kto,
        question=cleaned,
        lat=lat,
        lng=lng,
        intent=intent,
        patch=patch,
        context=context,
        pre_ota_region_prefixes=pre_ota_region_prefixes or [],
        legacy_client=legacy_client,
        emitter=emitter,
    )


_TALK_ANSWERS: dict[str, str] = {
    "unsupported": UNSUPPORTED_ANSWER,
    "smalltalk": BLANK_ANSWER,
}


async def _answer_without_searching(
    session: AsyncSession,
    redis: Redis,
    kto: KtoClient | None,
    *,
    intent: QueryIntent,
    context: AskContext | None,
    steps: list[AskStep],
    legacy_client: bool,
) -> AskResponse | None:
    if intent.task == "detail":
        target = detail_target(intent, context=context)
        if target is None:
            return None
        return await detail_service.answer_about_spot(
            session, redis, kto, content_id=target, intent=intent, steps=steps
        )
    sentence = _TALK_ANSWERS.get(intent.task)
    if sentence is None:
        return None
    return _talk_response(steps, intent, sentence, legacy_client=legacy_client)


def _with_dish_terms(
    intent: QueryIntent, *, question: str, context: AskContext | None
) -> QueryIntent:
    terms = retrieve.dish_search_terms(question)
    if not terms:
        return intent
    carried = set(context.intent.categoryKeywords) if context and context.intent else set()
    keywords = [keyword for keyword in intent.categoryKeywords if keyword not in carried]
    keywords.extend(term for term in terms if term not in keywords)
    return intent.model_copy(update={"categoryKeywords": keywords[:MAX_KEYWORDS]})


async def _pin_named_places(
    session: AsyncSession, kto: KtoClient | None, intent: QueryIntent
) -> tuple[list[ResolvedPlace], list[CandidateRow]]:
    if not intent.namedPlaces:
        return [], []
    resolved = await resolve_service.resolve_places(session, kto, intent.namedPlaces)
    content_ids = [
        place.spot.contentId
        for place in resolved
        if place.spot is not None and place.spot.contentId
    ]
    briefs = await repositories.load_candidates_by_ids(session, content_ids)
    return resolved, [briefs[cid] for cid in content_ids if cid in briefs]


async def _ask_with_question(
    session: AsyncSession,
    redis: Redis,
    kto: KtoClient | None,
    *,
    question: str,
    lat: float | None,
    lng: float | None,
    intent: QueryIntent | None,
    patch: RefinePatch | None,
    context: AskContext | None,
    pre_ota_region_prefixes: list[str],
    legacy_client: bool,
    emitter: Emitter | None = None,
) -> AskResponse:
    steps = Steps(emitter=emitter)
    if intent is not None:
        intent = refine_service.apply_patch(intent, patch)
    else:
        prior, prior_spots = _prior(context)
        label = CONTEXT_INTENT_LABEL if prior or prior_spots else "질문에서 지역·조건 추출"
        steps.begin("intent", label)
        outcome = await intent_service.resolve_intent(
            question, prior=prior, prior_spots=prior_spots
        )
        intent = outcome.intent
        if outcome.fallback:
            intent = await retrieve.reclassify_guessed_hints(session, intent)
        steps.append(
            AskStep(
                tool="intent",
                label=label,
                badge=INTENT_FALLBACK_BADGE if outcome.fallback else INTENT_MODEL_BADGE,
            )
        )
    if intent.outOfScope:
        raise AgentOutOfScope()
    if len(intent.subQuestions) > 1 and question.strip():
        split = await _ask_each(
            session, redis, kto, intent.subQuestions, lat=lat, lng=lng, steps=steps
        )
        if split is not None:
            return split
    answered = await _answer_without_searching(
        session,
        redis,
        kto,
        intent=intent,
        context=context,
        steps=steps,
        legacy_client=legacy_client,
    )
    if answered is not None:
        return answered
    intent = _with_dish_terms(intent, question=question, context=context)
    title_terms = retrieve.dish_search_terms(" ".join(intent.categoryKeywords))
    region = await region_service.resolve(
        session, redis, intent=intent, context=context, lat=lat, lng=lng
    )
    if region.guessed:
        intent = intent.model_copy(update={"regionHints": list(region.hints)})
        steps.append(
            AskStep(tool="intent", label=GUESSED_REGION_LABEL, badge=region.label or "현재 위치")
        )
    scene = scene_service.detect(question, list(intent.categoryKeywords))
    if scene is None and _asks_for_nothing(intent, prefixes=pre_ota_region_prefixes):
        sentence = NO_AXIS_ANSWER if question.strip() else BLANK_ANSWER
        return _talk_response(steps, intent, sentence, legacy_client=legacy_client)

    region_scope = await retrieve.resolve_region_scope(session, hints=intent.regionHints)
    pivot = _origin_anchor(intent, context, region_named=bool(region_scope.prefixes))
    if pivot is not None:
        return await _ask_with_anchor(
            session,
            pivot,
            lat=lat,
            lng=lng,
            prior_steps=steps,
            carried_intent=intent,
            title_terms=_title_terms_for_action(pivot.action, title_terms),
        )

    if intent.festivalOnly:
        return await _ask_festivals(
            session, redis, kto, intent=intent, steps=steps, lat=lat, lng=lng
        )

    resolved, pinned = await _pin_named_places(session, kto, intent)

    near = intent.nearMe and lat is not None and lng is not None
    keywords = _keywords(intent)
    category = await retrieve.resolve_category_scope(session, keywords)
    codes = category.codes
    eating = retrieve.food_action(codes) or retrieve.food_word(keywords)
    if eating is not None:
        return await _ask_for_food(
            session,
            action=eating,
            intent=intent,
            steps=steps,
            lat=lat,
            lng=lng,
            context=context,
            resolved=resolved,
            legacy_client=legacy_client,
            title_terms=_title_terms_for_action(eating, title_terms),
        )
    mood_ids = await repositories.find_mood_ids(session, list(intent.moodHints))
    scope = region_scope
    prefixes = scope.prefixes or pre_ota_region_prefixes
    if not scope.prefixes and pre_ota_region_prefixes:
        intent = intent.model_copy(update={"regionHints": list(pre_ota_region_prefixes)})
    region_widened: retrieve.RegionScope | None = None
    place_only = refine_service.named_place_is_the_only_constraint(
        intent, keywords=keywords, prefixes=prefixes, near=near
    )
    title_only = bool(keywords) and not codes and not mood_ids and not intent.indoorOnly
    if not place_only and not title_only:
        pinned = [
            row
            for row in pinned
            if retrieve.passes_filters(
                row,
                indoor_only=intent.indoorOnly,
                mood_ids=mood_ids,
                preference=intent.crowdPreference,
            )
        ]
    if intent.namedPlaces:
        steps.append(AskStep(tool="resolve_place", label="질문 속 장소 확인", badge=count(pinned)))

    near_is_a_cause = True
    ask = routes.Ask(
        session=session,
        steps=steps,
        intent=intent,
        scope=scope,
        category=category,
        prefixes=prefixes,
        keywords=keywords,
        mood_ids=mood_ids,
        pinned=pinned,
        lat=lat,
        lng=lng,
        near=near,
        place_only=place_only,
        title_only=title_only,
        scene=scene,
    )
    await routes.run_search(ask)
    intent = ask.intent
    prefixes = ask.prefixes
    candidates = ask.candidates
    axes = ask.axes
    region_widened = ask.widened

    pool = candidates
    if intent.crowdPreference != "any" and retrieve.has_crowd_signal(pool):
        pool = retrieve.filter_by_crowd(pool, intent.crowdPreference)
        steps.append(AskStep(tool="concentration", label="혼잡도로 추림", badge=count(pool)))

    if near and lat is not None and lng is not None and pool:
        pool = retrieve.sort_by_distance(pool, lat=lat, lng=lng)
        steps.append(AskStep(tool="nearby", label="현재 위치에서 가까운 순", badge=count(pool)))

    merged = _merge(pinned, pool)
    if not merged:
        if near and title_only:
            near_is_a_cause = bool(candidates)
        elif near and not place_only and not candidates:
            without_near = await ask.search(ask.searched_codes, prefixes, with_near=False)
            near_is_a_cause = bool(without_near)
            if near_is_a_cause:
                steps.append(
                    AskStep(
                        tool="nearby",
                        label=NEAR_PROBE_LABEL,
                        badge=count(without_near),
                    )
                )
        return _zero_response(
            steps,
            intent,
            has_coords=lat is not None and lng is not None and near_is_a_cause,
            region_hints=list(prefixes),
            keywords=[
                keyword
                for keyword in intent.categoryKeywords
                if title_only or keyword in category.matched
            ],
            axes=axes,
            legacy_client=legacy_client,
        )

    top = merged[: retrieve.RESULT_LIMIT]
    spots = [_card(row, intent=intent, lat=lat, lng=lng, near=near) for row in top]
    tag_basis = _tag_basis(top, spots, near=near)
    logger.info(
        "agent.ask.done",
        candidates=len(candidates),
        pool=len(pool),
        results=len(top),
        crowd=intent.crowdPreference,
    )
    spoken = searched_intent(
        intent,
        has_coords=lat is not None and lng is not None,
        region_hints=list(prefixes),
        keywords=[
            keyword
            for keyword in intent.categoryKeywords
            if title_only or keyword in category.matched
        ],
    )
    return AskResponse(
        steps=steps,
        answer=_answer(
            top, intent=spoken, near=near, lat=lat, lng=lng, region_widened=region_widened
        ),
        spots=spots,
        totalCount=len(spots),
        intent=intent,
        tagBasis=tag_basis,
        refinements=suggest_service.derive(
            intent,
            has_coords=lat is not None and lng is not None,
            result_count=len(spots),
            axes=axes,
            indoor_available=(
                any(row.indoor for row in merged) or len(candidates) >= retrieve.CANDIDATE_LIMIT
            ),
        ),
    )


async def _ask_each(
    session: AsyncSession,
    redis: Redis,
    kto: KtoClient | None,
    questions: list[str],
    *,
    lat: float | None,
    lng: float | None,
    steps: list[AskStep],
) -> AskResponse | None:
    """한 문장이 두세 가지를 함께 물으면 각각 따로 찾아 합친다.

    if/elif 라우터는 return 으로 경로 하나만 태우기 때문에 "여수 카페랑 축제" 에
    둘 다 줄 수 없었다. 조합마다 분기를 늘리는 대신 질문을 쪼갠다.
    """
    parts = await asyncio.gather(
        *(
            _ask_with_question(
                session,
                redis,
                kto,
                question=one,
                lat=lat,
                lng=lng,
                intent=None,
                patch=None,
                context=None,
                pre_ota_region_prefixes=[],
                legacy_client=False,
            )
            for one in questions
        ),
        return_exceptions=True,
    )
    answered = [part for part in parts if isinstance(part, AskResponse) and part.spots]
    if len(answered) < 2:
        return None

    spots: list[AgentSpotCard] = []
    seen: set[str] = set()
    for part in answered:
        for card in part.spots[:SUB_QUESTION_CARDS]:
            if card.contentId in seen:
                continue
            seen.add(card.contentId)
            spots.append(card)
    merged_steps = [*steps, *(step for part in answered for step in part.steps)]
    logger.info("agent.ask.split", asked=len(questions), answered=len(answered), spots=len(spots))
    return AskResponse(
        steps=merged_steps,
        answer=[AnswerSegment(text=f"{len(spots)}곳을 나눠서 찾았어요.")],
        spots=spots,
        totalCount=len(spots),
        intent=answered[0].intent.model_copy(update={"subQuestions": questions}),
        refinements=[],
        tagBasis=answered[0].tagBasis,
    )


async def _ask_festivals(
    session: AsyncSession,
    redis: Redis,
    kto: KtoClient | None,
    *,
    intent: QueryIntent,
    steps: list[AskStep],
    lat: float | None,
    lng: float | None,
) -> AskResponse:
    if kto is None:
        raise AgentNoResults()
    begin_step(steps, "festival", "오늘 열리는 축제 조회")
    try:
        pool = await feed_services.load_festival_pool(
            redis, kto, fetch_timeout=FESTIVAL_FETCH_BUDGET_SECONDS
        )
    except (AppError, TimeoutError) as exc:
        logger.warning("agent.festival.unavailable", error_type=type(exc).__name__)
        raise AgentFestivalUnavailable() from exc
    openable = await _openable_ids(session, pool)
    nationwide = _keep(pool, openable)
    fallback: str | None = None
    if intent.regionHints:
        scoped = _match_region(pool, intent.regionHints)
        cards = _keep(scoped, openable)
        if not cards:
            cards = nationwide
            fallback = _fallback_sentence(intent.regionHints[0], region_has_festivals=bool(scoped))
    else:
        cards = nationwide
    shown = [card for card in cards[: retrieve.RESULT_LIMIT] if card.content_id]
    rated = await repositories.find_rated_content_ids(
        session, [card.content_id or "" for card in shown]
    )
    spots = [
        AgentSpotCard(
            contentId=card.content_id or "",
            title=card.title,
            regionLabel=card.region_label,
            imageUrl=t1_display_url(card.image_url, card.cpyrht_div_cd),
            tag=card.dday,
            hasCrowd=card.content_id in rated,
        )
        for card in shown
    ]
    if not spots:
        raise AgentNoResults()
    steps.append(AskStep(tool="festival", label="오늘 열리는 축제 조회", badge=f"{len(spots)}곳"))
    answer = [
        AnswerSegment(text=spots[0].title, emphasis=True),
        AnswerSegment(text=f"{_subject_particle(spots[0].title)} 오늘 열려요. 오늘 열리는 축제로 "),
        AnswerSegment(text=f"{len(spots)}곳이에요."),
    ]
    if fallback is not None:
        answer.append(AnswerSegment(text=fallback))
    applied = QueryIntent(
        festivalOnly=True,
        regionHints=[] if fallback is not None else list(intent.regionHints),
    )
    return AskResponse(
        steps=steps,
        answer=answer,
        spots=spots,
        totalCount=len(spots),
        intent=applied,
        refinements=suggest_service.derive(
            applied,
            has_coords=lat is not None and lng is not None,
            result_count=len(spots),
        ),
    )


async def _openable_ids(
    session: AsyncSession, cards: list[feed_services.ChannelCardRow]
) -> set[str]:
    content_ids = [card.content_id for card in cards if card.content_id]
    if not content_ids:
        return set()
    return set(await load_active_spot_cards_by_ids(session, content_ids))


def _match_region(
    cards: list[feed_services.ChannelCardRow], hints: list[str]
) -> list[feed_services.ChannelCardRow]:
    hint_tokens = [tokens for hint in hints if (tokens := _region_tokens(hint))]
    if not hint_tokens:
        return []
    return [
        card for card in cards if any(_covers(tokens, card.region_label) for tokens in hint_tokens)
    ]


def _region_tokens(hint: str) -> list[str]:
    return [token for token in hint.split()[:MAX_HINT_TOKENS] if len(token) >= MIN_HINT_TOKEN_CHARS]


def _covers(tokens: list[str], region_label: str) -> bool:
    address = region_label.split()
    return all(_token_hits(token, address) for token in tokens)


def _token_hits(token: str, address: list[str]) -> bool:
    forms = (token, *SIDO_ALIASES.get(token, ()))
    return any(part.startswith(form) for part in address for form in forms)


def _keywords(intent: QueryIntent) -> list[str]:
    return list(intent.categoryKeywords)


def _asks_for_nothing(intent: QueryIntent, *, prefixes: list[str]) -> bool:
    return not (
        intent.categoryKeywords
        or intent.regionHints
        or intent.namedPlaces
        or intent.moodHints
        or intent.indoorOnly
        or intent.nearMe
        or intent.festivalOnly
        or intent.originPlace
        or intent.crowdPreference != "any"
        or prefixes
    )


def detail_target(intent: QueryIntent, context: AskContext | None) -> str | None:
    if context is None:
        return None
    if context.focusContentId is not None:
        return context.focusContentId
    wanted = (intent.targetPlace or "").strip()
    if not wanted:
        return context.spots[0].contentId if len(context.spots) == 1 else None
    exact = [spot for spot in context.spots if spot.title.strip() == wanted]
    if exact:
        return exact[0].contentId
    overlapping = [
        spot for spot in context.spots if wanted in spot.title or spot.title.strip() in wanted
    ]
    return overlapping[0].contentId if len(overlapping) == 1 else None


def _prior(context: AskContext | None) -> tuple[QueryIntent | None, list[str]]:
    if context is None:
        return None, []
    return context.intent, [spot.title for spot in context.spots]


def _origin_anchor(
    intent: QueryIntent, context: AskContext | None, *, region_named: bool = True
) -> AskAnchor | None:
    if context is None:
        return None
    if intent.originPlace is not None:
        wanted = intent.originPlace.strip()
        match = next((spot for spot in context.spots if spot.title.strip() == wanted), None)
        if match is not None:
            return AskAnchor(contentId=match.contentId, action=_origin_action(intent))
    if region_named and _named_a_new_region(intent, context):
        return None
    if context.focusContentId is not None and (intent.aroundOrigin or intent.nearMe):
        return AskAnchor(contentId=context.focusContentId, action=_origin_action(intent))
    return None


def _origin_action(intent: QueryIntent) -> AnchorAction:
    haystack = " ".join(intent.categoryKeywords)
    matched = next((action for word, action in ORIGIN_ACTION_WORDS if word in haystack), None)
    return matched or retrieve.food_word(list(intent.categoryKeywords)) or "nearby"


def _title_terms_for_action(action: AnchorAction, title_terms: list[str]) -> list[str]:
    return title_terms if action == "food" else []
