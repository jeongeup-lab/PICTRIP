from __future__ import annotations

import re

from app.core.logging import get_logger
from app.modules.agent.errors import AgentNoResults
from app.modules.agent.repositories import CandidateRow
from app.modules.agent.schemas import (
    MAX_CARD_CHIPS,
    AgentSpotCard,
    AnswerSegment,
    AskResponse,
    AskStep,
    DropAxis,
    QueryIntent,
)
from app.modules.agent.services import retrieve
from app.modules.agent.services import suggest as suggest_service
from app.modules.feed import services as feed_services

logger = get_logger(__name__)

PLACES_BASIS = "블로그 언급 기준"
RELATED_BASIS = "분위기 유사도 기준"
METERS_STEP = 10
DISTANCE_TAG = re.compile(r"^\d+(\.\d+)?(km|m)$")
PHOTO_BASIS = "사진 유사도 기준"
CALM_MIX_ALL = " 모두 사람이 적은 편이에요."
NARROW_HINT = " 마음에 드는 게 없으면 조건을 좁혀 말해주세요."
CROWD_LABELS = frozenset({"한산", "보통", "붐빔"})


def _addr_label(addr1: str | None) -> str:
    if not addr1:
        return ""
    return " ".join(addr1.split()[:2])


def _meters_label(meters: float) -> str:
    rounded = max(METERS_STEP, round(meters / METERS_STEP) * METERS_STEP)
    if rounded < 1000:
        return f"{rounded}m"
    return f"{meters / 1000:.1f}km"


def _km_label(km: float) -> str:
    return _meters_label(km * 1000)


def _is_distance_tag(tag: str | None) -> bool:
    return tag is not None and DISTANCE_TAG.match(tag) is not None


def _keep(
    cards: list[feed_services.ChannelCardRow], openable: set[str]
) -> list[feed_services.ChannelCardRow]:
    return [card for card in cards if card.content_id in openable]


def _fallback_sentence(hint: str, *, region_has_festivals: bool) -> str:
    if region_has_festivals:
        return f" {hint} 축제는 아직 상세 정보가 없어 전국에서 골랐어요."
    return f" {hint}에는 오늘 열리는 축제가 없어 전국에서 골랐어요."


def _named(unmapped: tuple[str, ...]) -> str:
    return "「" + " · ".join(unmapped) + "」"


def unknown_region_answer(unmapped: tuple[str, ...]) -> str:
    return f"{_named(unmapped)}라는 지역을 못 찾았어요. 어디로 찾아볼까요?"


def _unmapped_sentence(unmapped: tuple[str, ...]) -> list[AnswerSegment]:
    """말한 지역을 못 찾았으면 밝힌다.

    조용히 전국을 뒤져 20곳을 주면 사용자는 자기 지역이 무시된 걸 알 방법이 없다.
    """
    return [
        AnswerSegment(text=_named(unmapped), emphasis=True),
        AnswerSegment(text="라는 지역을 못 찾아서 전국에서 골랐어요."),
    ]


def _widen_sentence(scope: retrieve.RegionScope) -> list[AnswerSegment]:
    return [
        AnswerSegment(text=f"{scope.narrowed_label} 안에서는 찾지 못해 "),
        AnswerSegment(text=scope.widened_label, emphasis=True),
        AnswerSegment(text=" 전체에서 골랐어요."),
    ]


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
    card = retrieve.to_card(row, tag=_lead_tag(row, intent=intent, lat=lat, lng=lng, near=near))
    return card.model_copy(update={"chips": _chips(row, card, lat=lat, lng=lng, near=near)})


def _lead_tag(
    row: CandidateRow,
    *,
    intent: QueryIntent,
    lat: float | None,
    lng: float | None,
    near: bool,
) -> str | None:
    if near and lat is not None and lng is not None:
        km = retrieve.distance_km(row, lat=lat, lng=lng)
        if km is not None:
            return _km_label(km)
    if intent.crowdPreference == "quiet" and row.percentile is not None:
        return f"하위 {row.percentile}%"
    return retrieve.crowd_label(row)


def _chips(
    row: CandidateRow,
    card: AgentSpotCard,
    *,
    lat: float | None,
    lng: float | None,
    near: bool,
) -> list[str]:
    """이 곳이 왜 뽑혔는지를 곳마다 다른 값으로만 말한다.

    같은 종류를 두 번 세지 않는다 — '하위 1%' 옆에 '한산' 을 붙이면 한 신호가 두 칸을
    먹는다. 조건 줄이 이미 말하는 것(실내·한적·지역)도 넣지 않는다.
    """
    chips: list[str] = []
    if near and lat is not None and lng is not None:
        km = retrieve.distance_km(row, lat=lat, lng=lng)
        if km is not None:
            chips.append(_km_label(km))
    crowd = f"하위 {row.percentile}%" if row.percentile is not None else retrieve.crowd_label(row)
    if crowd is not None:
        chips.append(crowd)
    if card.tag and card.tag not in chips:
        chips.insert(0, card.tag)
    return chips[:MAX_CARD_CHIPS]


def _answer_opening(intent: QueryIntent) -> str:
    conditions = applied_conditions(intent, axes=suggest_service.ALL_AXES)
    if not conditions:
        return "조건에 맞는 곳으로 "
    return f"{' + '.join(conditions)} 조건으로 "


def _scope_sentence(top: list[CandidateRow], *, intent: QueryIntent) -> list[AnswerSegment]:
    return [
        AnswerSegment(text=_answer_opening(intent)),
        AnswerSegment(text=f"{len(top)}곳이에요."),
    ]


def _lead_sentence(
    top: list[CandidateRow],
    *,
    intent: QueryIntent,
    near: bool,
    lat: float | None,
    lng: float | None,
    region_widened: retrieve.RegionScope | None,
) -> list[AnswerSegment]:
    if region_widened is not None:
        return _widen_sentence(region_widened)
    if intent.crowdPreference == "quiet":
        pcts = [row.percentile for row in top if row.percentile is not None]
        if pcts:
            return [
                AnswerSegment(text="혼잡도 "),
                AnswerSegment(text=f"하위 {max(pcts)}%", emphasis=True),
                AnswerSegment(text=" 안쪽으로만 골랐어요."),
            ]
    if near and lat is not None and lng is not None:
        return _nearest_sentence(top, lat=lat, lng=lng)
    return []


def _nearest_sentence(top: list[CandidateRow], *, lat: float, lng: float) -> list[AnswerSegment]:
    kms = [km for row in top if (km := retrieve.distance_km(row, lat=lat, lng=lng)) is not None]
    if not kms:
        return []
    return [
        AnswerSegment(text="가장 가까운 곳이 "),
        AnswerSegment(text=_km_label(min(kms)), emphasis=True),
        AnswerSegment(text="예요."),
    ]


def _calm_mix_sentence(top: list[CandidateRow]) -> list[AnswerSegment]:
    labelled = [row for row in top if retrieve.crowd_label(row) is not None]
    if not labelled:
        return []
    calm = [row for row in labelled if retrieve.crowd_label(row) == "한산"]
    if not calm:
        return []
    if len(calm) == len(top):
        return [AnswerSegment(text=CALM_MIX_ALL)]
    return [
        AnswerSegment(text=" 이 중 "),
        AnswerSegment(text=f"{len(calm)}곳", emphasis=True),
        AnswerSegment(text="은 사람이 적은 편이에요."),
    ]


def _answer(
    top: list[CandidateRow],
    *,
    intent: QueryIntent,
    near: bool,
    lat: float | None,
    lng: float | None,
    region_widened: retrieve.RegionScope | None = None,
    unmapped: tuple[str, ...] = (),
) -> list[AnswerSegment]:
    lead = (
        _unmapped_sentence(unmapped)
        if unmapped
        else _lead_sentence(
            top, intent=intent, near=near, lat=lat, lng=lng, region_widened=region_widened
        )
    )
    scope = _scope_sentence(top, intent=intent)
    if not lead:
        mix = _calm_mix_sentence(top)
        if mix:
            return [*scope, *mix]
        return [*scope, AnswerSegment(text=NARROW_HINT)]
    return [*lead, AnswerSegment(text=" "), *scope]


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


def applied_conditions(intent: QueryIntent, *, axes: frozenset[DropAxis]) -> list[str]:
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
    conditions = applied_conditions(intent, axes=axes)
    way_out = (
        " 지역을 넓히면 나올 수 있어요."
        if intent.regionHints
        else " 조건을 조금 바꿔서 다시 물어봐 주세요."
    )
    if not conditions:
        return [
            AnswerSegment(text="이 조건으로는 없어요."),
            AnswerSegment(text=way_out),
        ]
    return [
        AnswerSegment(text=" + ".join(conditions), emphasis=True),
        AnswerSegment(text=" 조건으로는 없어요."),
        AnswerSegment(text=way_out),
    ]


def _talk_response(steps: list[AskStep], intent: QueryIntent, sentence: str) -> AskResponse:
    logger.info("agent.ask.talk", task=intent.task)
    return AskResponse(
        steps=steps,
        answer=[AnswerSegment(text=sentence)],
        spots=[],
        totalCount=0,
        intent=intent,
        refinements=[],
    )


def _zero_response(
    steps: list[AskStep],
    intent: QueryIntent,
    *,
    has_coords: bool,
    region_hints: list[str],
    keywords: list[str],
    axes: frozenset[DropAxis],
) -> AskResponse:
    searched = searched_intent(
        intent, has_coords=has_coords, region_hints=region_hints, keywords=keywords
    )
    refinements = suggest_service.derive_for_zero(searched, has_coords=has_coords, axes=axes)
    conditions = applied_conditions(searched, axes=axes)
    if not conditions:
        raise AgentNoResults()
    logger.info("agent.ask.zero", conditions=len(conditions), releasable=len(refinements))
    return AskResponse(
        steps=steps,
        answer=_zero_answer(searched, axes=axes),
        spots=[],
        totalCount=0,
        intent=searched,
        refinements=refinements,
    )


def _crowd_basis(rows: list[CandidateRow]) -> str | None:
    days = {row.base_ymd for row in rows if row.base_ymd is not None}
    if not days:
        return None
    if len(days) > 1:
        return "혼잡도 예측 기준"
    day = days.pop()
    return f"혼잡도 {day.month}/{day.day} 예측 기준"


def _is_crowd_tag(tag: str | None) -> bool:
    if tag is None:
        return False
    return tag in CROWD_LABELS or tag.startswith("하위 ")


def _tag_basis(rows: list[CandidateRow], spots: list[AgentSpotCard], *, near: bool) -> str | None:
    if near and spots and all(_is_distance_tag(spot.tag) for spot in spots):
        return "직선거리 기준"
    if any((spot.tag or "").startswith("유사도 ") for spot in spots):
        return PHOTO_BASIS
    if any(_is_crowd_tag(spot.tag) for spot in spots):
        return _crowd_basis(rows)
    return None


def _without_unapplied_axes(intent: QueryIntent) -> QueryIntent:
    return intent.model_copy(
        update={"crowdPreference": "any", "indoorOnly": False, "moodHints": []}
    )


def _dish_title_condition(title_terms: list[str]) -> str:
    return f"상호에 요청한 음식명({' · '.join(title_terms)})이 모두 들어간 곳"


def _rebadge_last(steps: list[AskStep], tool: str, badge: str) -> None:
    for index in reversed(range(len(steps))):
        if steps[index].tool == tool:
            steps[index] = steps[index].model_copy(update={"badge": badge})
            return
