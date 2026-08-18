from __future__ import annotations

import asyncio

from app.core.db import AsyncSession
from app.core.logging import get_logger
from app.modules.agent import repositories
from app.modules.agent.emitter import Emitter, Steps
from app.modules.agent.errors import AgentNoResults
from app.modules.agent.repositories import CandidateRow, VectorMatchRow
from app.modules.agent.schemas import (
    AgentSpotCard,
    AnswerSegment,
    AskResponse,
    AskStep,
    DropAxis,
    QueryIntent,
    RefinePatch,
)
from app.modules.agent.services import intent as intent_service
from app.modules.agent.services import photo as photo_service
from app.modules.agent.services import refine as refine_service
from app.modules.agent.services import retrieve
from app.modules.agent.services import suggest as suggest_service
from app.modules.agent.services.anchor import _subject_particle
from app.modules.agent.services.answer import (
    _km_label,
    _nearest_sentence,
    _rebadge_last,
    _tag_basis,
    _widen_sentence,
    _zero_response,
)
from app.modules.agent.services.routes import count, widen_label
from app.web.errors import AppError

logger = get_logger(__name__)

PHOTO_AXES: frozenset[DropAxis] = frozenset({"near", "region"})
INTENT_MODEL_BADGE = "AI 해석"
INTENT_FALLBACK_BADGE = "사전 매칭"


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
    emitter: Emitter | None = None,
) -> AskResponse:
    steps = Steps(emitter=emitter)
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
                    AskStep(
                        tool="intent", label="덧붙인 말에서 조건 추출", badge=INTENT_MODEL_BADGE
                    )
                )
            except AppError as exc:
                logger.warning("agent.photo.intent_fallback", code=exc.code)
                intent = intent_service.fallback_intent(question or "")
                steps.append(
                    AskStep(
                        tool="intent",
                        label="덧붙인 말에서 조건 추출",
                        badge=INTENT_FALLBACK_BADGE,
                    )
                )

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
        steps.append(AskStep(tool="photo_match", label=widen_label(scope), badge="pgvector"))

    similarity = {row.content_id: photo_service.similarity(row) for row in rows}
    if near and lat is not None and lng is not None and rows:
        ordered = sorted(
            ordered, key=lambda row: retrieve.distance_km(row, lat=lat, lng=lng) or 0.0
        )
        steps.append(AskStep(tool="nearby", label="현재 위치에서 가까운 순", badge=count(ordered)))

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
    return AskResponse(
        steps=steps,
        answer=_photo_answer(top, spots, near=near, lat=lat, lng=lng, widened=widened),
        spots=spots,
        totalCount=len(spots),
        intent=intent,
        tagBasis=_tag_basis(top, spots, near=near),
        refinements=suggest_service.derive(
            intent,
            has_coords=lat is not None and lng is not None,
            result_count=len(spots),
            axes=PHOTO_AXES,
            indoor_available=any(row.indoor for row in ordered),
        ),
    )


def _photo_answer(
    top: list[CandidateRow],
    spots: list[AgentSpotCard],
    *,
    near: bool,
    lat: float | None,
    lng: float | None,
    widened: retrieve.RegionScope | None,
) -> list[AnswerSegment]:
    lead: list[AnswerSegment] = []
    if near and lat is not None and lng is not None:
        lead = _nearest_sentence(top, lat=lat, lng=lng)
    if not lead:
        lead = [
            AnswerSegment(text=spots[0].title, emphasis=True),
            AnswerSegment(text=f"{_subject_particle(spots[0].title)} 가장 비슷해요."),
        ]
    answer = [
        *lead,
        AnswerSegment(text=" 사진과 닮은 곳으로 "),
        AnswerSegment(text=f"{len(top)}곳이에요."),
    ]
    if widened is not None:
        answer.append(AnswerSegment(text=" "))
        answer.extend(_widen_sentence(widened))
    answer.append(AnswerSegment(text=" 원본 사진은 비교 후 바로 폐기했어요."))
    return answer


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
            return retrieve.to_card(row, tag=_km_label(km))
    return retrieve.to_card(row, tag=f"유사도 {round(similarity.get(row.content_id, 0.0) * 100)}%")
