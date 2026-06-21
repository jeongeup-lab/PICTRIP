"""CRS draft-course generation.

`build_draft_courses` turns one base spot into three candidate itineraries
(efficient / mood / calm). Drafts are NOT persisted: each call recomputes the
three orderings deterministically from the same inputs.

Candidate spots come exclusively from the SPT service (embedding neighbors of
the base) - CRS never touches SPT models or the DB directly for spot data,
honoring the cross-module import rule.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.courses.schemas import CompanionType, CourseType, DurationType, PaceType
from app.modules.courses.services.rows import CourseItemCard
from app.modules.spots.services import SpotCardRow, find_similar_spots

# Strategy order is the response contract - stable across calls.
STRATEGIES: tuple[CourseType, ...] = ("efficient", "mood", "calm")

# How many stops (base + candidates) a full itinerary holds, by trip length.
_STOPS_BY_DURATION: dict[DurationType, int] = {
    "day": 4,
    "1n2d": 6,
    "2n3d": 8,
    "3n_plus": 10,
}
# calm trims this many stops off the full count (quieter = fewer stops).
_CALM_TRIM = 2


@dataclass(frozen=True)
class DraftCourse:
    strategy: CourseType
    items: list[CourseItemCard]


def _planar_distance(a: SpotCardRow, b: SpotCardRow) -> float:
    """Squared planar distance in (mapx, mapy) degrees.

    KTO mapx/mapy are WGS84 lon/lat; across the small span inside one course a
    planar metric ranks proximity identically to great-circle distance and
    avoids trig. Spots missing coordinates are treated as +inf (sort last).
    """
    if a.mapx is None or a.mapy is None or b.mapx is None or b.mapy is None:
        return float("inf")
    dx = a.mapx - b.mapx
    dy = a.mapy - b.mapy
    return dx * dx + dy * dy


def _order_efficient(base: SpotCardRow, candidates: list[SpotCardRow]) -> list[SpotCardRow]:
    """Greedy nearest-neighbor tour from the base spot to minimize travel.

    Starts at base, repeatedly hops to the closest unvisited candidate. Ties
    (and coordinate-less spots) broken by content_id for determinism.
    """
    remaining = list(candidates)
    ordered = [base]
    current = base
    while remaining:
        nxt = min(remaining, key=lambda c: (_planar_distance(current, c), c.content_id))
        ordered.append(nxt)
        remaining.remove(nxt)
        current = nxt
    return ordered


def _order_mood(base: SpotCardRow, ranked: list[tuple[SpotCardRow, float]]) -> list[SpotCardRow]:
    """Order by embedding similarity to the base (ascending cosine distance).

    `ranked` already arrives sorted by distance from SPT; re-sort with a
    content_id tie-break so equal-distance spots are fully deterministic.
    """
    ordered_pairs = sorted(ranked, key=lambda p: (p[1], p[0].content_id))
    return [base, *[row for row, _ in ordered_pairs]]


def _order_calm(base: SpotCardRow, candidates: list[SpotCardRow]) -> list[SpotCardRow]:
    """Quieter itinerary: dispersed stops, and (via the caller) fewer of them.

    Crowd data (CrowdMetric) is not yet wired into SPT, so 'calm' uses a
    documented fallback: spread stops out (descending distance from base) so
    the day feels unhurried rather than densely packed, and the caller trims
    the stop count. Deterministic via content_id tie-break.
    """
    spread = sorted(candidates, key=lambda c: (-_spread_key(base, c), c.content_id))
    return [base, *spread]


def _spread_key(a: SpotCardRow, b: SpotCardRow) -> float:
    """Distance for the 'calm' spread sort; coordinate-less spots -> 0."""
    d = _planar_distance(a, b)
    return 0.0 if d == float("inf") else d


def _to_items(rows: list[SpotCardRow]) -> list[CourseItemCard]:
    return [
        CourseItemCard(
            position=i,
            content_id=r.content_id,
            title=r.title,
            first_image_url=r.first_image_url,
            addr1=r.addr1,
            mapx=r.mapx,
            mapy=r.mapy,
        )
        for i, r in enumerate(rows)
    ]


async def build_draft_courses(
    session: AsyncSession,
    *,
    base_content_id: str,
    duration: DurationType,
    pace: PaceType,
    companion: CompanionType,
) -> list[DraftCourse]:
    """Produce the three candidate draft courses for a base spot.

    `pace` / `companion` are accepted for contract completeness but do not yet
    alter ordering (only stop-count, via duration, does); a later iteration can
    weight them. Raises ResourceNotFound (via SPT) if the base spot is absent.
    """
    _ = (pace, companion)  # reserved for future weighting; keeps the contract explicit

    full_stops = _STOPS_BY_DURATION.get(duration, 6)
    # +1 for the base itself; floor so 'calm' (full - trim) still keeps >=1 stop.
    want_candidates = max(full_stops - 1, _CALM_TRIM + 1)

    similar = await find_similar_spots(session, base_content_id, limit=want_candidates)
    base = similar.query  # raises ResourceNotFound above if the base is unknown
    ranked = similar.neighbors  # [(SpotCardRow, distance)], ascending distance
    candidates = [row for row, _ in ranked]

    efficient_rows = _order_efficient(base, candidates)[:full_stops]
    mood_rows = _order_mood(base, ranked)[:full_stops]
    calm_count = max(full_stops - _CALM_TRIM, 1)
    calm_rows = _order_calm(base, candidates)[:calm_count]

    by_strategy: dict[CourseType, list[SpotCardRow]] = {
        "efficient": efficient_rows,
        "mood": mood_rows,
        "calm": calm_rows,
    }
    return [
        DraftCourse(strategy=strategy, items=_to_items(by_strategy[strategy]))
        for strategy in STRATEGIES
    ]
