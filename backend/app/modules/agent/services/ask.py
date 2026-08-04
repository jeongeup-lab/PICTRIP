from __future__ import annotations

import asyncio

from redis.asyncio import Redis

from app.core.db import AsyncSession
from app.core.logging import get_logger
from app.kto.client import KtoClient
from app.kto.display import t1_display_url
from app.modules.agent import repositories
from app.modules.agent.errors import (
    AgentFestivalUnavailable,
    AgentNoResults,
    AgentOutOfScope,
)
from app.modules.agent.repositories import CandidateRow, VectorMatchRow
from app.modules.agent.schemas import (
    MAX_HINT_TOKENS,
    AgentSpotCard,
    AnswerSegment,
    AskAnchor,
    AskResponse,
    AskStep,
    DropAxis,
    QueryIntent,
    RefinePatch,
)
from app.modules.agent.services import intent as intent_service
from app.modules.agent.services import photo as photo_service
from app.modules.agent.services import refine as refine_service
from app.modules.agent.services import resolve as resolve_service
from app.modules.agent.services import retrieve
from app.modules.agent.services import suggest as suggest_service
from app.modules.feed import services as feed_services
from app.modules.spots.services import (
    NearbyCategory,
    NearbySpotRow,
    find_nearby_spots,
    load_active_spot_cards_by_ids,
)
from app.web.errors import AppError, ValidationFailed

logger = get_logger(__name__)

INDOOR_RETRY_LABEL = "실내로만 다시 조회"
FESTIVAL_FETCH_BUDGET_SECONDS = 4.0
ANCHOR_RADIUS_M = 3000
ANCHOR_CATEGORIES: dict[str, NearbyCategory] = {
    "food": NearbyCategory.food,
    "cafe": NearbyCategory.cafe,
    "nearby": NearbyCategory.attraction,
}
ANCHOR_NOUNS: dict[str, str] = {"food": "맛집", "cafe": "카페", "nearby": "볼거리"}
PHOTO_AXES: frozenset[DropAxis] = frozenset({"near", "region"})
TITLE_AXES: frozenset[DropAxis] = frozenset({"category", "near", "region"})
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
    pre_ota_region_prefixes: list[str] | None = None,
    legacy_client: bool = False,
) -> AskResponse:
    cleaned = (question or "").strip()
    if anchor is not None:
        if image_bytes is not None:
            raise ValidationFailed("anchor cannot be combined with photo")
        return await _ask_with_anchor(session, anchor, lat=lat, lng=lng)
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
        pre_ota_region_prefixes=pre_ota_region_prefixes or [],
        legacy_client=legacy_client,
    )


async def _ask_with_photo(
    session: AsyncSession,
    *,
    question: str,
    image_bytes: bytes,
    image_mime: str | None,
    lat: float | None,
    lng: float | None,
    intent: QueryIntent | None,
    patch: RefinePatch | None,
    pre_ota_region_prefixes: list[str],
    legacy_client: bool,
) -> AskResponse:
    steps: list[AskStep] = []
    intent_task = (
        asyncio.create_task(intent_service.extract_intent(question))
        if question and intent is None
        else None
    )
    try:
        vector = await photo_service.embed_photo(image_bytes=image_bytes, image_mime=image_mime)
    except BaseException:
        if intent_task is not None:
            intent_task.cancel()
        raise
    if intent is not None:
        intent = refine_service.apply_patch(intent, patch)
    else:
        intent = QueryIntent()
        if intent_task is not None:
            try:
                intent = await intent_task
                steps.append(
                    AskStep(tool="intent", label="덧붙인 말에서 조건 추출", badge="Gemini")
                )
            except AppError as exc:
                logger.warning("agent.photo.intent_skipped", code=exc.code)

    scope = await retrieve.resolve_region_scope(session, hints=intent.regionHints)
    prefixes = scope.prefixes or pre_ota_region_prefixes
    if not scope.prefixes and pre_ota_region_prefixes:
        intent = intent.model_copy(update={"regionHints": list(pre_ota_region_prefixes)})
    near = intent.nearMe and lat is not None and lng is not None

    async def matched(within: list[str]) -> tuple[list[VectorMatchRow], list[CandidateRow]]:
        try:
            found = await photo_service.match_vector(session, vector, region_prefixes=within)
        except AgentNoResults:
            return [], []
        briefs = await repositories.load_candidates_by_ids(
            session, [row.content_id for row in found]
        )
        usable = [briefs[row.content_id] for row in found if row.content_id in briefs]
        if near:
            usable = [row for row in usable if row.lat is not None and row.lng is not None]
        return found, usable

    rows, ordered = await matched(prefixes)
    steps.append(AskStep(tool="photo_match", label=_photo_label(prefixes), badge="pgvector"))
    widened: retrieve.RegionScope | None = None
    if not ordered and scope.widenable:
        prefixes = scope.sido_prefixes
        rows, ordered = await matched(prefixes)
        widened = scope
        intent = intent.model_copy(update={"regionHints": list(scope.sido_prefixes)})
        steps.append(AskStep(tool="photo_match", label=_widen_label(scope), badge="pgvector"))

    similarity = {row.content_id: photo_service.similarity(row) for row in rows}
    if near and lat is not None and lng is not None:
        ordered = sorted(
            ordered, key=lambda row: retrieve.distance_km(row, lat=lat, lng=lng) or 0.0
        )
        steps.append(AskStep(tool="nearby", label="현재 위치에서 가까운 순", badge=_count(ordered)))

    if not ordered:
        _rebadge_last(steps, "photo_match", f"{len(rows)}곳")
        return _zero_response(
            steps,
            intent,
            has_coords=lat is not None and lng is not None and bool(rows),
            region_hints=list(prefixes),
            keywords=list(intent.categoryKeywords),
            axes=PHOTO_AXES,
            legacy_client=legacy_client,
        )

    top = ordered[: retrieve.RESULT_LIMIT]
    spots = [_photo_card(row, similarity=similarity, lat=lat, lng=lng, near=near) for row in top]
    answer = [
        AnswerSegment(text="사진과 닮은 곳으로 "),
        AnswerSegment(text=f"{len(top)}곳", emphasis=True),
        AnswerSegment(text=" 찾았어요."),
    ]
    if widened is not None:
        answer.extend(_widen_sentence(widened))
    answer.append(AnswerSegment(text=" 원본 사진은 비교 후 바로 폐기했어요."))
    return AskResponse(
        steps=steps,
        answer=answer,
        spots=spots,
        totalCount=len(spots),
        intent=intent,
        refinements=suggest_service.derive(
            intent,
            has_coords=lat is not None and lng is not None,
            result_count=len(spots),
            axes=PHOTO_AXES,
            indoor_available=any(row.indoor for row in ordered),
        ),
    )


def _photo_label(prefixes: list[str]) -> str:
    if prefixes:
        return f"{prefixes[0]} 안에서 사진과 닮은 곳 비교"
    return "사진을 CLIP으로 임베딩해 벡터 비교"


def _photo_card(
    row: CandidateRow,
    *,
    similarity: dict[str, float],
    lat: float | None,
    lng: float | None,
    near: bool,
) -> AgentSpotCard:
    if near and lat is not None and lng is not None:
        km = retrieve.distance_km(row, lat=lat, lng=lng)
        if km is not None:
            return retrieve.to_card(row, tag=f"{km:.1f}km")
    return retrieve.to_card(row, tag=f"유사도 {round(similarity.get(row.content_id, 0.0) * 100)}%")


async def _ask_with_anchor(
    session: AsyncSession, anchor: AskAnchor, *, lat: float | None, lng: float | None
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
    )
    kept = [near for near in found if row is None or near.content_id != row.content_id]
    kept = kept[: retrieve.RESULT_LIMIT]
    if not kept:
        raise AgentNoResults()
    rated = await repositories.load_candidates_by_ids(session, [n.content_id for n in kept])
    spots = [_anchor_card(near, has_crowd=_has_crowd(rated.get(near.content_id))) for near in kept]
    steps = [AskStep(tool="nearby", label=f"{origin} 주변 {noun} 조회", badge=f"{len(spots)}곳")]
    answer = [
        AnswerSegment(text=f"{origin} 주변 {noun} "),
        AnswerSegment(text=f"{len(spots)}곳", emphasis=True),
        AnswerSegment(text=" 찾았어요."),
    ]
    nearest = kept[0].dist
    if nearest is not None:
        answer.append(AnswerSegment(text=" 가장 가까운 곳은 "))
        answer.append(AnswerSegment(text=_meters_label(nearest), emphasis=True))
        answer.append(AnswerSegment(text=" 거리예요."))
    logger.info("agent.anchor.done", action=anchor.action, results=len(spots))
    return AskResponse(
        steps=steps,
        answer=answer,
        spots=spots,
        totalCount=len(spots),
        intent=QueryIntent(),
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


def _has_crowd(row: CandidateRow | None) -> bool:
    return row is not None and row.concentration_rate is not None


def _anchor_card(row: NearbySpotRow, *, has_crowd: bool) -> AgentSpotCard:
    return AgentSpotCard(
        contentId=row.content_id,
        title=row.title,
        regionLabel=_addr_label(row.addr1),
        imageUrl=t1_display_url(row.first_image_url, row.cpyrht_div_cd),
        tag=_meters_label(row.dist) if row.dist is not None else None,
        lat=row.mapy,
        lng=row.mapx,
        hasCrowd=has_crowd,
    )


def _addr_label(addr1: str | None) -> str:
    if not addr1:
        return ""
    return " ".join(addr1.split()[:2])


def _meters_label(meters: float) -> str:
    return f"{meters / 1000:.1f}km"


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
    pre_ota_region_prefixes: list[str],
    legacy_client: bool,
) -> AskResponse:
    steps: list[AskStep] = []
    if intent is not None:
        intent = refine_service.apply_patch(intent, patch)
    else:
        intent = await intent_service.extract_intent(question)
        steps.append(AskStep(tool="intent", label="질문에서 지역·조건 추출", badge="Gemini"))
    if intent.outOfScope:
        raise AgentOutOfScope()

    if intent.festivalOnly:
        return await _ask_festivals(
            session, redis, kto, intent=intent, steps=steps, lat=lat, lng=lng
        )

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

    near = intent.nearMe and lat is not None and lng is not None
    keywords = _keywords(intent)
    category = await retrieve.resolve_category_scope(session, keywords)
    codes = category.codes
    mood_ids = await repositories.find_mood_ids(session, list(intent.moodHints))
    scope = await retrieve.resolve_region_scope(session, hints=intent.regionHints)
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
        steps.append(AskStep(tool="resolve_place", label="질문 속 장소 확인", badge=_count(pinned)))

    axes = suggest_service.ALL_AXES
    if place_only:
        if not pinned:
            raise AgentNoResults()
        candidates = []
    elif title_only:
        axes = TITLE_AXES
        candidates = await retrieve.search_by_title(session, keywords, region_prefixes=prefixes)
        steps.append(
            AskStep(
                tool="title_search",
                label=f"{keywords[0]} 이름으로 조회",
                badge=_count(candidates),
            )
        )
        if not _locatable(candidates, near=near) and not pinned and scope.widenable:
            prefixes = scope.sido_prefixes
            candidates = await retrieve.search_by_title(session, keywords, region_prefixes=prefixes)
            region_widened = scope
            intent = intent.model_copy(update={"regionHints": list(scope.sido_prefixes)})
            steps.append(
                AskStep(
                    tool="title_search",
                    label=_widen_label(scope),
                    badge=_count(candidates),
                )
            )
    else:
        preference = intent.crowdPreference
        indoor_only = intent.indoorOnly

        async def search(within_codes: list[str], within_prefixes: list[str]) -> list[CandidateRow]:
            return await retrieve.search_candidates(
                session,
                codes=within_codes,
                region_prefixes=within_prefixes,
                preference=preference,
                lat=lat,
                lng=lng,
                near=near,
                indoor_only=indoor_only,
                mood_ids=mood_ids,
            )

        candidates = await search(codes, prefixes)
        steps.append(
            AskStep(
                tool="category_search",
                label=_search_label(keywords, prefixes, indoor=indoor_only),
                badge=_count(candidates),
            )
        )
        if not _locatable(candidates, near=near) and not pinned and scope.widenable:
            prefixes = scope.sido_prefixes
            candidates = await search(codes, prefixes)
            region_widened = scope
            intent = intent.model_copy(update={"regionHints": list(scope.sido_prefixes)})
            steps.append(
                AskStep(
                    tool="category_search",
                    label=_widen_label(scope),
                    badge=_count(candidates),
                )
            )
        if not candidates and indoor_only and codes:
            candidates = await search([], prefixes)
            intent = intent.model_copy(update={"categoryKeywords": []})
            steps.append(
                AskStep(
                    tool="category_search",
                    label=INDOOR_RETRY_LABEL,
                    badge=_count(candidates),
                )
            )
        if mood_ids:
            steps.append(
                AskStep(tool="mood_search", label="분위기로 추림", badge=_count(candidates))
            )

    pool = candidates
    if intent.crowdPreference != "any" and retrieve.has_crowd_signal(pool):
        pool = retrieve.filter_by_crowd(pool, intent.crowdPreference)
        steps.append(AskStep(tool="concentration", label="혼잡도로 추림", badge=_count(pool)))

    if near and lat is not None and lng is not None:
        pool = retrieve.sort_by_distance(pool, lat=lat, lng=lng)
        steps.append(AskStep(tool="nearby", label="현재 위치에서 가까운 순", badge=_count(pool)))

    merged = _merge(pinned, pool)
    if not merged:
        return _zero_response(
            steps,
            intent,
            has_coords=lat is not None and lng is not None and (not title_only or bool(candidates)),
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
    logger.info(
        "agent.ask.done",
        candidates=len(candidates),
        pool=len(pool),
        results=len(top),
        crowd=intent.crowdPreference,
    )
    return AskResponse(
        steps=steps,
        answer=_answer(
            top, intent=intent, near=near, lat=lat, lng=lng, region_widened=region_widened
        ),
        spots=spots,
        totalCount=len(spots),
        intent=intent,
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
        AnswerSegment(text="오늘 열리는 축제로 "),
        AnswerSegment(text=f"{len(spots)}곳", emphasis=True),
        AnswerSegment(text=" 찾았어요."),
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


def _keep(
    cards: list[feed_services.ChannelCardRow], openable: set[str]
) -> list[feed_services.ChannelCardRow]:
    return [card for card in cards if card.content_id in openable]


def _fallback_sentence(hint: str, *, region_has_festivals: bool) -> str:
    if region_has_festivals:
        return f" {hint} 축제는 아직 상세 정보가 없어 전국에서 골랐어요."
    return f" {hint}에는 오늘 열리는 축제가 없어 전국에서 골랐어요."


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


def _locatable(rows: list[CandidateRow], *, near: bool) -> list[CandidateRow]:
    if not near:
        return rows
    return [row for row in rows if row.lat is not None and row.lng is not None]


def _widen_label(scope: retrieve.RegionScope) -> str:
    return f"{scope.narrowed_label} 결과 없음 — {scope.widened_label}로 넓힘"


def _widen_sentence(scope: retrieve.RegionScope) -> list[AnswerSegment]:
    return [
        AnswerSegment(text=f". {scope.narrowed_label} 안에서는 찾지 못해 "),
        AnswerSegment(text=scope.widened_label, emphasis=True),
        AnswerSegment(text=" 전체에서 골랐어요."),
    ]


def _search_label(keywords: list[str], prefixes: list[str], *, indoor: bool) -> str:
    if indoor:
        head = "실내"
    elif keywords:
        head = " · ".join(keywords[:2])
    elif prefixes:
        head = prefixes[0]
    else:
        head = "전국"
    return f"{head} 관광지 조회"


def _merge(pinned: list[CandidateRow], pool: list[CandidateRow]) -> list[CandidateRow]:
    seen = {row.content_id for row in pinned}
    return pinned + [row for row in pool if row.content_id not in seen]


def _card(
    row: CandidateRow,
    *,
    intent: QueryIntent,
    lat: float | None,
    lng: float | None,
    near: bool,
) -> AgentSpotCard:
    if near and lat is not None and lng is not None:
        km = retrieve.distance_km(row, lat=lat, lng=lng)
        if km is not None:
            return retrieve.to_card(row, tag=f"{km:.1f}km")
    if intent.crowdPreference == "quiet" and row.percentile is not None:
        return retrieve.to_card(row, tag=f"하위 {row.percentile}%")
    return retrieve.to_card(row, tag=retrieve.crowd_label(row))


def _answer(
    top: list[CandidateRow],
    *,
    intent: QueryIntent,
    near: bool,
    lat: float | None,
    lng: float | None,
    region_widened: retrieve.RegionScope | None = None,
) -> list[AnswerSegment]:
    segments = [AnswerSegment(text="조건에 맞는 곳으로 ")]
    segments.append(AnswerSegment(text=f"{len(top)}곳", emphasis=True))
    segments.append(AnswerSegment(text=" 추렸어요"))

    if region_widened is not None:
        segments.extend(_widen_sentence(region_widened))
        return segments
    if intent.crowdPreference == "quiet":
        pcts = [row.percentile for row in top if row.percentile is not None]
        if pcts:
            segments.append(AnswerSegment(text=". 모두 이 조건 안에서 혼잡도 "))
            segments.append(AnswerSegment(text=f"하위 {max(pcts)}%", emphasis=True))
            segments.append(AnswerSegment(text=" 안쪽이에요."))
            return segments
    if near and lat is not None and lng is not None:
        kms = [km for row in top if (km := retrieve.distance_km(row, lat=lat, lng=lng)) is not None]
        if kms:
            segments.append(AnswerSegment(text=". 가장 가까운 곳은 "))
            segments.append(AnswerSegment(text=f"{min(kms):.1f}km", emphasis=True))
            segments.append(AnswerSegment(text=" 거리예요."))
            return segments
    segments.append(AnswerSegment(text=". 마음에 드는 게 없으면 조건을 좁혀 말해주세요."))
    return segments


def _count(rows: list[CandidateRow]) -> str:
    return f"{len(rows)}곳"


def _rebadge_last(steps: list[AskStep], tool: str, badge: str) -> None:
    for index in reversed(range(len(steps))):
        if steps[index].tool == tool:
            steps[index] = steps[index].model_copy(update={"badge": badge})
            return


def searched_intent(
    intent: QueryIntent,
    *,
    has_coords: bool,
    region_hints: list[str],
    keywords: list[str],
) -> QueryIntent:
    update: dict[str, object] = {}
    if list(intent.regionHints) != region_hints:
        update["regionHints"] = list(region_hints)
    if list(intent.categoryKeywords) != keywords:
        update["categoryKeywords"] = list(keywords)
    if not has_coords and intent.nearMe:
        update["nearMe"] = False
    return intent.model_copy(update=update) if update else intent


def _applied_conditions(intent: QueryIntent, *, axes: frozenset[DropAxis]) -> list[str]:
    labels: list[str] = []
    if "region" in axes and intent.regionHints:
        labels.append(intent.regionHints[0])
    if "category" in axes and (intent.categoryKeywords or intent.moodHints):
        labels.append(suggest_service.category_noun(intent))
    if "indoor" in axes and intent.indoorOnly:
        labels.append("실내")
    if "crowd" in axes:
        if intent.crowdPreference == "quiet":
            labels.append("한적")
        elif intent.crowdPreference == "popular":
            labels.append("유명한 곳")
    if "near" in axes and intent.nearMe:
        labels.append("내 근처")
    return labels


def _zero_answer(intent: QueryIntent, *, axes: frozenset[DropAxis]) -> list[AnswerSegment]:
    conditions = _applied_conditions(intent, axes=axes)
    head = f"{' + '.join(conditions)} 조건" if conditions else "이 조건"
    segments = [
        AnswerSegment(text=f"{head}으로는 "),
        AnswerSegment(text="0곳", emphasis=True),
        AnswerSegment(text="이에요."),
    ]
    segments.append(AnswerSegment(text=" 조건 하나를 풀면 찾을 수 있어요."))
    return segments


def _zero_response(
    steps: list[AskStep],
    intent: QueryIntent,
    *,
    has_coords: bool,
    region_hints: list[str],
    keywords: list[str],
    axes: frozenset[DropAxis],
    legacy_client: bool,
) -> AskResponse:
    searched = searched_intent(
        intent, has_coords=has_coords, region_hints=region_hints, keywords=keywords
    )
    refinements = suggest_service.derive_for_zero(searched, has_coords=has_coords, axes=axes)
    if not refinements or legacy_client:
        raise AgentNoResults()
    conditions = _applied_conditions(searched, axes=axes)
    logger.info("agent.ask.zero", conditions=len(conditions), releasable=len(refinements))
    return AskResponse(
        steps=steps,
        answer=_zero_answer(searched, axes=axes),
        spots=[],
        totalCount=0,
        intent=searched,
        refinements=refinements,
    )
