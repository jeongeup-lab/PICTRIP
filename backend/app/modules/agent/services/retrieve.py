from __future__ import annotations

from app.core.db import AsyncSession
from app.kto.display import t1_display_url
from app.modules.agent import repositories
from app.modules.agent.repositories import CandidateOrder, CandidateRow
from app.modules.agent.schemas import AgentSpotCard, CrowdPreference, Region, Who
from app.modules.agent.services.geo import haversine_km
from app.modules.spots.services import map_region_tokens_to_sido, search_spots_by_title

CANDIDATE_LIMIT = 400
TITLE_KEYWORD_LIMIT = 3
TITLE_MATCH_LIMIT = 20
RESULT_LIMIT = 20
QUIET_KEEP_RATIO = 0.3
POPULAR_KEEP_RATIO = 0.3
BUSY_RATE = 70.0
CALM_RATE = 30.0

REGION_PREFIXES: dict[Region, tuple[str, ...]] = {
    "all": (),
    "capital": ("서울", "경기", "인천"),
    "gangwon": ("강원",),
    "chungcheong": ("충청", "충북", "충남", "대전", "세종"),
    "jeolla": ("전라", "전북", "전남", "광주"),
    "gyeongsang": ("경상", "경북", "경남", "대구", "울산", "부산"),
    "jeju": ("제주",),
}

REGION_LABELS: dict[Region, str] = {
    "all": "전국",
    "capital": "수도권",
    "gangwon": "강원",
    "chungcheong": "충청",
    "jeolla": "전라",
    "gyeongsang": "경상",
    "jeju": "제주",
}

WHO_KEYWORDS: dict[Who, tuple[str, ...]] = {
    "any": (),
    "solo": (),
    "duo": (),
    "kids": ("테마파크", "동물원", "체험"),
    "pets": ("공원", "산책로"),
}

INDOOR_KEYWORDS = ("박물관", "미술관", "전시관", "아쿠아리움", "공연장", "체험관")


async def resolve_category_codes(session: AsyncSession, keywords: list[str]) -> list[str]:
    codes: list[str] = []
    for keyword in keywords:
        for code in await repositories.find_category_codes(session, keyword):
            if code not in codes:
                codes.append(code)
    return codes


async def resolve_region_prefixes(
    session: AsyncSession, *, region: Region, hints: list[str]
) -> list[str]:
    if hints:
        tokens = {token for hint in hints for token in _hint_tokens(hint)}
        mapping = await map_region_tokens_to_sido(session, tokens)
        if mapping:
            return sorted(set(mapping.values()))
    return list(REGION_PREFIXES[region])


def _hint_tokens(hint: str) -> list[str]:
    cleaned = hint.strip()
    tokens = cleaned.split()
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
) -> list[CandidateRow]:
    quiet = preference == "quiet"

    async def query(*, ceiling: int | None, floor: int | None) -> list[CandidateRow]:
        return await repositories.find_candidates(
            session,
            codes=codes or None,
            region_prefixes=region_prefixes or None,
            limit=CANDIDATE_LIMIT,
            order=candidate_order(preference=preference, near=near),
            rated_only=preference != "any",
            percentile_ceiling=ceiling,
            percentile_floor=floor,
            lat=lat,
            lng=lng,
        )

    if preference == "any":
        return await query(ceiling=None, floor=None)
    within = await query(
        ceiling=round(QUIET_KEEP_RATIO * 100) if quiet else None,
        floor=None if quiet else 100 - round(POPULAR_KEEP_RATIO * 100),
    )
    return within or await query(ceiling=None, floor=None)


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
    )
