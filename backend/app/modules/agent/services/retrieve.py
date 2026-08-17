from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from app.core.db import AsyncSession
from app.kto.display import t1_display_url
from app.modules.agent import repositories
from app.modules.agent.repositories import INDOOR_L2 as INDOOR_L2
from app.modules.agent.repositories import INDOOR_L3 as INDOOR_L3
from app.modules.agent.repositories import CandidateOrder, CandidateRow
from app.modules.agent.schemas import (
    MAX_HINT_TOKENS,
    MAX_KEYWORDS,
    AgentSpotCard,
    CrowdPreference,
    QueryIntent,
)
from app.modules.agent.services.geo import haversine_km
from app.modules.spots.services import (
    NearbyCategory,
    RegionPrefix,
    category_sql,
    map_region_tokens_to_prefixes,
    search_spots_by_title,
)

CANDIDATE_LIMIT = 400
TITLE_KEYWORD_LIMIT = 3
TITLE_MATCH_LIMIT = 20
RESULT_LIMIT = 20
QUIET_KEEP_RATIO = 0.3
POPULAR_KEEP_RATIO = 0.3
BUSY_RATE = 70.0
CALM_RATE = 30.0


@dataclass(frozen=True, slots=True)
class CategoryScope:
    codes: list[str]
    matched: list[str]


CAFE_CODES = ("FD05", "FD030100")
FOOD_PREFIX = "FD"


CAFE_WORDS = ("카페", "커피", "찻집", "디저트", "베이커리", "빵집", "제과점")
FOOD_WORDS = ("맛집", "음식", "식당", "먹을", "먹거리", "밥집")
FOOD_SUFFIXES = ("집", "전문점", "포차", "주점", "술집")
DISH_WORDS = (
    "삼겹살",
    "불고기",
    "국밥",
    "냉면",
    "칼국수",
    "국수",
    "파스타",
    "피자",
    "치킨",
    "초밥",
    "라멘",
    "짜장면",
    "짬뽕",
    "돈까스",
    "곱창",
    "막창",
    "족발",
    "보쌈",
    "해물",
    "한정식",
    "브런치",
)
EXACT_DISH_WORDS = frozenset({"회", "고기", "구이", "찜", "탕"})
MIN_FOOD_SUFFIX_CHARS = 2
DISH_PARTICLES = frozenset({"", "을", "를", "이", "가", "은", "는", "도", "만", "로", "으로"})
DISH_PLACE_SUFFIXES = frozenset((*FOOD_SUFFIXES, "맛집", "식당"))
DISH_NEGATIONS = frozenset({"말고", "빼고", "대신", "아닌", "제외", "제외한", "제외하고"})
GENERIC_EATING_WORDS = frozenset((*FOOD_WORDS, *CAFE_WORDS))


def _targets_dish(token: str, word: str) -> bool:
    if not token.startswith(word):
        return False
    suffix = token[len(word) :]
    if suffix in DISH_PARTICLES:
        return True
    return any(
        suffix.startswith(place_suffix) and suffix[len(place_suffix) :] in DISH_PARTICLES
        for place_suffix in DISH_PLACE_SUFFIXES
    )


def _generic_eating_token(token: str) -> bool:
    return any(
        token == f"{word}{particle}" for word in GENERIC_EATING_WORDS for particle in DISH_PARTICLES
    )


def _specific_place_term(token: str) -> str | None:
    if _generic_eating_token(token):
        return None
    endings = (
        f"{place_suffix}{particle}"
        for place_suffix in sorted(DISH_PLACE_SUFFIXES, key=len, reverse=True)
        for particle in sorted(DISH_PARTICLES, key=len, reverse=True)
    )
    for ending in endings:
        if token.endswith(ending):
            term = token[: -len(ending)]
            return term if len(term) >= MIN_FOOD_SUFFIX_CHARS else None
    return None


def dish_search_terms(question: str) -> list[str]:
    tokens = re.findall(r"[가-힣]+", question)
    replacements = [index for index, token in enumerate(tokens) if token in DISH_NEGATIONS]
    if replacements:
        tokens = tokens[replacements[-1] + 1 :]
    picked: list[str] = []
    positions: list[int] = []
    known_words = (*DISH_WORDS, *sorted(EXACT_DISH_WORDS))
    for index, token in enumerate(tokens):
        term = next((word for word in known_words if _targets_dish(token, word)), None)
        term = term or _specific_place_term(token)
        if term is None:
            continue
        positions.append(index)
        if not any(term in existing for existing in picked):
            picked.append(term)
    cafe_positions = [
        index for index, token in enumerate(tokens) if any(word in token for word in CAFE_WORDS)
    ]
    if positions and cafe_positions and cafe_positions[-1] > positions[-1]:
        return []
    return picked


def food_word(keywords: list[str]) -> Literal["food", "cafe"] | None:
    if not keywords:
        return None
    picked = {_eating(word) for word in keywords}
    return picked.pop() if len(picked) == 1 and None not in picked else None


def _eating(word: str) -> Literal["food", "cafe"] | None:
    if any(hint in word for hint in CAFE_WORDS):
        return "cafe"
    if any(hint in word for hint in FOOD_WORDS):
        return "food"
    if word in EXACT_DISH_WORDS:
        return "food"
    if any(hint in word for hint in DISH_WORDS):
        return "food"
    if len(word) >= MIN_FOOD_SUFFIX_CHARS and word.endswith(FOOD_SUFFIXES):
        return "food"
    return None


def food_action(codes: list[str]) -> Literal["food", "cafe"] | None:
    if not codes or not all(code.startswith(FOOD_PREFIX) for code in codes):
        return None
    if all(code.startswith(CAFE_CODES) for code in codes):
        return "cafe"
    return "food"


TAXONOMY_SYNONYMS: dict[str, str] = {
    "사찰": "불교",
    "절": "불교",
    "템플스테이": "불교",
    "교회": "기독교",
    "성당": "기독교",
    "놀이공원": "테마파크",
    "식물원": "수목원",
    "트레킹": "둘레길",
}


def taxonomy_word(keyword: str) -> str:
    return TAXONOMY_SYNONYMS.get(keyword, keyword)


async def resolve_category_scope(session: AsyncSession, keywords: list[str]) -> CategoryScope:
    codes: list[str] = []
    matched: list[str] = []
    for keyword in keywords:
        found = await repositories.find_category_codes(session, taxonomy_word(keyword))
        if found:
            matched.append(keyword)
        for code in found:
            if code not in codes:
                codes.append(code)
    return CategoryScope(codes=codes, matched=matched)


async def resolve_category_codes(session: AsyncSession, keywords: list[str]) -> list[str]:
    return (await resolve_category_scope(session, keywords)).codes


@dataclass(frozen=True, slots=True)
class RegionScope:
    prefixes: list[str]
    sido_prefixes: list[str]
    narrowed_hints: tuple[str, ...] = ()
    narrowed_sidos: tuple[str, ...] = ()

    @property
    def widenable(self) -> bool:
        return bool(self.narrowed_hints) and self.sido_prefixes != self.prefixes

    @property
    def narrowed_label(self) -> str:
        return " · ".join(self.narrowed_hints)

    @property
    def widened_label(self) -> str:
        return " · ".join(self.narrowed_sidos) or "인근 시도"


EMPTY_REGION_SCOPE = RegionScope(prefixes=[], sido_prefixes=[])


async def resolve_region_scope(session: AsyncSession, *, hints: list[str]) -> RegionScope:
    if not hints:
        return EMPTY_REGION_SCOPE
    tokens = {token for hint in hints for token in _hint_tokens(hint)}
    mapping = await map_region_tokens_to_prefixes(session, tokens)
    if not mapping:
        return EMPTY_REGION_SCOPE
    narrowed = [
        (token, resolved) for token, resolved in sorted(mapping.items()) if resolved.narrowed
    ]
    return RegionScope(
        prefixes=_drop_covered({resolved.prefix for resolved in mapping.values()}),
        sido_prefixes=sorted({resolved.sido for resolved in mapping.values()}),
        narrowed_hints=tuple(token for token, _ in narrowed),
        narrowed_sidos=tuple(dict.fromkeys(resolved.sido for _, resolved in narrowed)),
    )


def _drop_covered(prefixes: set[str]) -> list[str]:
    return sorted(
        prefix
        for prefix in prefixes
        if not any(other.startswith(f"{prefix} ") for other in prefixes)
    )


async def resolve_region_prefixes(session: AsyncSession, *, hints: list[str]) -> list[str]:
    return (await resolve_region_scope(session, hints=hints)).prefixes


def split_unmappable_hints(
    hints: list[str], mapping: dict[str, RegionPrefix]
) -> tuple[list[str], list[str]]:
    kept: list[str] = []
    dropped: list[str] = []
    for hint in hints:
        target = kept if any(token in mapping for token in _hint_tokens(hint)) else dropped
        target.append(hint)
    return kept, dropped


def reclassified_intent(intent: QueryIntent, *, kept: list[str], dropped: list[str]) -> QueryIntent:
    keywords = list(intent.categoryKeywords)
    for word in dropped:
        if word and word not in keywords:
            keywords.append(word)
    return intent.model_copy(
        update={"regionHints": kept, "categoryKeywords": keywords[:MAX_KEYWORDS]}
    )


async def reclassify_guessed_hints(session: AsyncSession, intent: QueryIntent) -> QueryIntent:
    if not intent.regionHints:
        return intent
    tokens = {token for hint in intent.regionHints for token in _hint_tokens(hint)}
    mapping = await map_region_tokens_to_prefixes(session, tokens)
    kept, dropped = split_unmappable_hints(intent.regionHints, mapping)
    if not dropped:
        return intent
    return reclassified_intent(intent, kept=kept, dropped=dropped)


def _hint_tokens(hint: str) -> list[str]:
    cleaned = hint.strip()
    tokens = cleaned.split()[:MAX_HINT_TOKENS]
    return [cleaned, *tokens] if len(tokens) > 1 else tokens


async def search_candidates(
    session: AsyncSession,
    *,
    codes: list[str],
    region_prefixes: list[str],
    preference: CrowdPreference,
    lat: float | None,
    lng: float | None,
    near: bool,
    indoor_only: bool = False,
    mood_ids: list[int] | None = None,
    pool_sql: str | None = None,
    title_terms: list[str] | None = None,
    theme: repositories.BuzzTheme = "spot",
) -> list[CandidateRow]:
    quiet = preference == "quiet"

    async def query(*, ceiling: int | None, floor: int | None) -> list[CandidateRow]:
        return await repositories.find_candidates(
            session,
            theme=theme,
            codes=codes or None,
            region_prefixes=region_prefixes or None,
            limit=CANDIDATE_LIMIT,
            order=candidate_order(preference=preference, near=near),
            rated_only=preference != "any",
            percentile_ceiling=ceiling,
            percentile_floor=floor,
            lat=lat,
            lng=lng,
            indoor_only=indoor_only,
            mood_ids=mood_ids,
            pool_sql=pool_sql,
            title_terms=title_terms,
        )

    if preference == "any":
        return await query(ceiling=None, floor=None)
    within = await query(
        ceiling=round(QUIET_KEEP_RATIO * 100) if quiet else None,
        floor=None if quiet else 100 - round(POPULAR_KEEP_RATIO * 100),
    )
    return within or await query(ceiling=None, floor=None)


async def search_food(
    session: AsyncSession,
    *,
    action: str,
    region_prefixes: list[str],
    preference: CrowdPreference = "any",
    indoor_only: bool = False,
    mood_ids: list[int] | None = None,
    lat: float | None = None,
    lng: float | None = None,
    near: bool = False,
    title_terms: list[str] | None = None,
) -> list[CandidateRow]:
    pool = NearbyCategory.cafe if action == "cafe" else NearbyCategory.food
    return await search_candidates(
        session,
        theme="cafe" if action == "cafe" else "food",
        codes=[],
        region_prefixes=region_prefixes,
        preference=preference,
        lat=lat,
        lng=lng,
        near=near,
        indoor_only=indoor_only,
        mood_ids=mood_ids,
        pool_sql=category_sql(pool),
        title_terms=title_terms,
    )


async def search_by_title(
    session: AsyncSession, keywords: list[str], *, region_prefixes: list[str]
) -> list[CandidateRow]:
    hints: list[str | None] = list(region_prefixes) if region_prefixes else [None]
    content_ids: list[str] = []
    for keyword in keywords[:TITLE_KEYWORD_LIMIT]:
        for hint in hints:
            rows = await search_spots_by_title(
                session, keyword, region_hint=hint, limit=TITLE_MATCH_LIMIT
            )
            for row in rows:
                if row.content_id not in content_ids:
                    content_ids.append(row.content_id)
    briefs = await repositories.load_candidates_by_ids(session, content_ids)
    found = [briefs[cid] for cid in content_ids if cid in briefs]
    if not region_prefixes:
        return found
    return [row for row in found if row.addr1 and row.addr1.startswith(tuple(region_prefixes))]


def sort_by_distance(rows: list[CandidateRow], *, lat: float, lng: float) -> list[CandidateRow]:
    locatable = [row for row in rows if row.lat is not None and row.lng is not None]
    return sorted(locatable, key=lambda row: distance_km(row, lat=lat, lng=lng) or 0.0)


def candidate_order(*, preference: CrowdPreference, near: bool) -> CandidateOrder:
    if near:
        return "distance"
    if preference == "quiet":
        return "rate_asc"
    if preference == "popular":
        return "rate_desc"
    return "id"


def has_crowd_signal(rows: list[CandidateRow]) -> bool:
    return any(row.percentile is not None for row in rows)


def filter_by_crowd(rows: list[CandidateRow], preference: CrowdPreference) -> list[CandidateRow]:
    if preference == "any":
        return rows
    rated = [row for row in rows if row.percentile is not None]
    if not rated:
        return rows
    quiet = preference == "quiet"
    ceiling = round(QUIET_KEEP_RATIO * 100)
    floor = 100 - round(POPULAR_KEEP_RATIO * 100)

    def passes(row: CandidateRow) -> bool:
        rank = row.percentile or 0
        return rank <= ceiling if quiet else rank >= floor

    kept = [row for row in rated if passes(row)]
    if kept:
        return kept
    extreme = sorted(
        rated, key=lambda row: (row.percentile or 0, row.content_id), reverse=not quiet
    )
    return extreme[:RESULT_LIMIT]


def passes_filters(
    row: CandidateRow,
    *,
    indoor_only: bool,
    mood_ids: list[int],
    preference: CrowdPreference,
) -> bool:
    if indoor_only and not row.indoor:
        return False
    if mood_ids and not set(mood_ids) & set(row.mood_ids):
        return False
    if preference == "any":
        return True
    if row.concentration_rate is None:
        return False
    if preference == "quiet":
        return row.concentration_rate <= CALM_RATE
    return row.concentration_rate >= BUSY_RATE


def distance_km(row: CandidateRow, *, lat: float, lng: float) -> float | None:
    if row.lat is None or row.lng is None:
        return None
    return haversine_km(lat, lng, row.lat, row.lng)


def crowd_label(row: CandidateRow) -> str | None:
    if row.concentration_rate is None:
        return None
    if row.concentration_rate >= BUSY_RATE:
        return "붐빔"
    if row.concentration_rate <= CALM_RATE:
        return "한산"
    return "보통"


def region_label(row: CandidateRow) -> str:
    parts = [part for part in (row.region_name, row.sigungu_name) if part]
    if parts:
        return " ".join(parts)
    return row.addr1 or ""


def to_card(row: CandidateRow, *, tag: str | None) -> AgentSpotCard:
    return AgentSpotCard(
        contentId=row.content_id,
        title=row.title,
        regionLabel=region_label(row),
        imageUrl=t1_display_url(row.image_url, row.cpyrht_div_cd),
        tag=tag,
        lat=row.lat,
        lng=row.lng,
        categoryGroup=row.category_group,
        hasCrowd=row.concentration_rate is not None,
    )
