from __future__ import annotations

from app.core.db import AsyncSession
from app.kto.display import t1_display_url
from app.modules.agent import repositories
from app.modules.agent.repositories import CandidateRow
from app.modules.agent.schemas import AgentSpotCard, CrowdPreference, Region, Who
from app.modules.agent.services.geo import haversine_km

CANDIDATE_LIMIT = 400
RESULT_LIMIT = 4
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


async def search_candidates(
    session: AsyncSession, *, codes: list[str], region: Region
) -> list[CandidateRow]:
    prefixes = list(REGION_PREFIXES[region])
    return await repositories.find_candidates(
        session,
        codes=codes or None,
        region_prefixes=prefixes or None,
        limit=CANDIDATE_LIMIT,
    )


def filter_by_crowd(rows: list[CandidateRow], preference: CrowdPreference) -> list[CandidateRow]:
    rated = [row for row in rows if row.concentration_rate is not None]
    if preference == "any" or not rated:
        return rows
    ascending = preference == "quiet"
    ratio = QUIET_KEEP_RATIO if ascending else POPULAR_KEEP_RATIO
    ordered = sorted(
        rated,
        key=lambda row: (row.concentration_rate or 0.0, row.content_id),
        reverse=not ascending,
    )
    keep = max(1, int(len(ordered) * ratio))
    return ordered[:keep]


def sort_by_distance(rows: list[CandidateRow], *, lat: float, lng: float) -> list[CandidateRow]:
    locatable = [row for row in rows if row.lat is not None and row.lng is not None]
    return sorted(locatable, key=lambda row: distance_km(row, lat=lat, lng=lng) or 0.0)


def distance_km(row: CandidateRow, *, lat: float, lng: float) -> float | None:
    if row.lat is None or row.lng is None:
        return None
    return haversine_km(lat, lng, row.lat, row.lng)


def percentile(row: CandidateRow, pool: list[CandidateRow]) -> int | None:
    if row.concentration_rate is None:
        return None
    rated = [r.concentration_rate for r in pool if r.concentration_rate is not None]
    if not rated:
        return None
    below = sum(1 for rate in rated if rate < row.concentration_rate)
    return max(1, round(below / len(rated) * 100))


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
