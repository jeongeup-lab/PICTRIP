from __future__ import annotations

from collections.abc import Mapping, Sequence
from itertools import pairwise
from typing import Any, cast

from app.modules.agent import repositories
from app.modules.agent.repositories import CandidateRow
from app.modules.agent.schemas import MAX_KEYWORDS, MAX_REGION_HINTS, CrowdPreference
from app.modules.agent.services import retrieve
from app.modules.agent.services.geo import haversine_km
from app.modules.agent.tools.base import Tool, ToolContext, ToolResult, recoverable, strings

MAX_DAYS = 4
PER_DAY = 3
_UNKNOWN = "그 이름을 지역으로 해석하지 못했습니다. 시도·시군구 이름으로 다시 부르세요."
_EMPTY = "그 지역에는 일정에 넣을 곳이 없습니다."


OUTLIER_KM = 60


def _placed(rows: Sequence[CandidateRow]) -> list[CandidateRow]:
    return [row for row in rows if row.lat is not None and row.lng is not None]


def _without_outliers(rows: list[CandidateRow]) -> list[CandidateRow]:
    """무리에서 멀리 떨어진 곳을 떤다.

    좌표가 지역과 안 맞는 스팟이 실제로 있다 — 경주 황성공원이 춘천 좌표를 달고
    있어 2일차 이동거리가 319km 로 나왔다.
    """
    if len(rows) < 3:
        return rows
    lat = sorted(cast(float, row.lat) for row in rows)[len(rows) // 2]
    lng = sorted(cast(float, row.lng) for row in rows)[len(rows) // 2]
    kept = [
        row
        for row in rows
        if haversine_km(lat, lng, cast(float, row.lat), cast(float, row.lng)) <= OUTLIER_KM
    ]
    return kept or rows


def _chain(rows: list[CandidateRow]) -> list[CandidateRow]:
    """가장 가까운 곳을 이어 붙인다 — 최적 경로가 아니라 되돌아가지 않는 동선이다."""
    if not rows:
        return []
    remaining = list(rows)
    ordered = [remaining.pop(0)]
    while remaining:
        last = ordered[-1]
        nearest = min(
            remaining,
            key=lambda row: haversine_km(
                cast(float, last.lat),
                cast(float, last.lng),
                cast(float, row.lat),
                cast(float, row.lng),
            ),
        )
        remaining.remove(nearest)
        ordered.append(nearest)
    return ordered


def _legs_km(ordered: Sequence[CandidateRow]) -> float:
    return sum(
        haversine_km(cast(float, a.lat), cast(float, a.lng), cast(float, b.lat), cast(float, b.lng))
        for a, b in pairwise(ordered)
    )


def days_of(args: Mapping[str, Any]) -> int:
    raw = args.get("days")
    if not isinstance(raw, int) or raw < 1:
        return 2
    return min(raw, MAX_DAYS)


def _crowd(args: Mapping[str, Any]) -> CrowdPreference:
    value = args.get("crowd")
    return cast(CrowdPreference, value) if value in ("quiet", "any", "popular") else "any"


async def _sights(
    ctx: ToolContext, keywords: list[str], prefixes: list[str], crowd: CrowdPreference
) -> list[CandidateRow]:
    codes = await retrieve.resolve_category_codes(ctx.session, keywords)
    return await retrieve.search_candidates(
        ctx.session,
        repositories.CandidateQuery(
            limit=retrieve.CANDIDATE_LIMIT, codes=codes or None, region_prefixes=prefixes
        ),
        preference=crowd,
        near=False,
    )


def _meal_words(keywords: list[str]) -> list[str]:
    return [word for word in keywords if retrieve.food_word([word]) is not None]


def _slots(eating: list[str]) -> list[tuple[str, list[str]]]:
    """구체 음식은 각자 풀을 갖는다 — 제목 조건이 AND 라 '국밥 초밥' 은 교집합이 빈다."""
    slots: dict[tuple[str, str], tuple[str, list[str]]] = {}
    for word in eating:
        action = retrieve.food_word([word])
        if action is None:
            continue
        dishes = retrieve.dish_search_terms(word) if action == "food" else []
        slots.setdefault((action, dishes[0] if dishes else ""), (action, dishes))
    return list(slots.values())


async def _meals(
    ctx: ToolContext, eating: list[str], prefixes: list[str], crowd: CrowdPreference
) -> list[list[CandidateRow]]:
    """맛집과 카페는 풀이 달라 한 번에 못 뽑는다 — 요청한 종류마다 따로 돌려준다."""
    pools: list[list[CandidateRow]] = []
    for action, dishes in _slots(eating):
        found = await retrieve.search_food(
            ctx.session,
            action=action,
            region_prefixes=prefixes,
            preference=crowd,
            title_terms=dishes or None,
        )
        pools.append(_without_outliers(_placed(found)))
    return [pool for pool in pools if pool]


def _nearest(leg: Sequence[CandidateRow], pool: Sequence[CandidateRow]) -> CandidateRow | None:
    if not leg or not pool:
        return None
    head = leg[0]
    return min(
        pool,
        key=lambda row: haversine_km(
            cast(float, head.lat),
            cast(float, head.lng),
            cast(float, row.lat),
            cast(float, row.lng),
        ),
    )


async def _plan_itinerary(ctx: ToolContext, args: Mapping[str, Any]) -> ToolResult:
    hints = strings(args, "regions", limit=MAX_REGION_HINTS)
    if not hints:
        return ToolResult(rows=[], observation="regions 가 비었습니다.")

    region = hints[0]
    prefixes = await retrieve.resolve_region_prefixes(ctx.session, hints=[region])
    if not prefixes:
        return ToolResult(rows=[], observation=f"{region}: {_UNKNOWN}")

    keywords = strings(args, "categories", limit=MAX_KEYWORDS)
    eating = _meal_words(keywords)
    crowd = _crowd(args)
    seeing = [word for word in keywords if word not in eating]

    meals = await _meals(ctx, eating, prefixes, crowd)
    sights = await _sights(ctx, seeing, prefixes, crowd)

    return _assemble(
        region,
        sights=_without_outliers(_placed(sights)),
        meals=meals,
        days=days_of(args),
    )


def _assemble(
    region: str, *, sights: list[CandidateRow], meals: list[list[CandidateRow]], days: int
) -> ToolResult:
    """맛집은 일정에 끼워 넣는 한 끼다 — 볼거리를 대신하지 않는다.

    볼거리가 아예 없는 지역에서만 맛집이 일정 자체가 된다.
    """
    if not sights:
        sights, meals = ([row for pool in meals for row in pool], [])
    per_day = PER_DAY - len(meals) if meals else PER_DAY
    ordered = _chain(sights[: days * max(per_day, 1)])
    if not ordered:
        return ToolResult(rows=[], observation=f"{region}: {_EMPTY}")

    left = [list(pool) for pool in meals]
    lines: list[str] = []
    plan: list[CandidateRow] = []
    for day in range(days):
        leg = ordered[day * per_day : (day + 1) * per_day]
        if not leg:
            break
        leg = _chain([*leg, *_one_of_each(leg, left)])
        plan.extend(leg)
        names = " → ".join(row.title for row in leg)
        lines.append(f"{day + 1}일차: {names} (직선거리 {round(_legs_km(leg))}km)")

    plan_text = f"{region} {len(lines)}일 일정 — " + " / ".join(lines)
    if len(lines) < days:
        plan_text += f" (요청한 {days}일을 채울 곳이 부족해 {len(lines)}일로 줄였습니다)"
    return ToolResult(rows=plan, observation=plan_text, fact=plan_text)


def _one_of_each(
    leg: Sequence[CandidateRow], pools: list[list[CandidateRow]]
) -> list[CandidateRow]:
    """종류마다 하루 한 곳씩 — 거리만 보면 모든 날이 식당으로 채워진다."""
    picked: list[CandidateRow] = []
    for pool in pools:
        chosen = _nearest(leg, pool)
        if chosen is not None:
            pool.remove(chosen)
            picked.append(chosen)
    return picked


PLAN_ITINERARY = Tool(
    name="plan_itinerary",
    description=(
        "지역과 일수를 받아 일자별 동선을 짠다. '통영 2박3일 짜줘' 같은 질문에 쓴다. "
        "가까운 곳끼리 묶어 되돌아가지 않게 잇는다. 단순 목록을 원하면 category_search 를 쓴다."
    ),
    parameters={
        "type": "object",
        "properties": {
            "regions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "일정을 짤 지역 하나. 여러 개를 줘도 첫 번째만 쓴다. 예: ['통영'].",
            },
            "days": {
                "type": "integer",
                "minimum": 1,
                "maximum": MAX_DAYS,
                "description": "일수. 2박3일이면 3. 비우면 2, 최대 4.",
            },
            "categories": {
                "type": "array",
                "items": {"type": "string"},
                "description": "넣고 싶은 장소 종류. 비우면 전체.",
            },
            "crowd": {
                "type": "string",
                "enum": ["quiet", "any", "popular"],
                "description": "혼잡도 선호.",
            },
        },
        "required": ["regions"],
    },
    label=lambda args: f"{(strings(args, 'regions', limit=1) or ['지역'])[0]} 일정 짜기",
    run=recoverable(_plan_itinerary),
)
