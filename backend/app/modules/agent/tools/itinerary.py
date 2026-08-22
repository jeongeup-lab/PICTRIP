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
_NEEDS_REGION = "어느 지역으로 갈지 알려주시면 일정을 짜드릴게요."
_UNKNOWN_FACT = "{region} 이(가) 어디인지 못 알아들었어요. 시나 군 이름으로 알려주세요."
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


OUTSIDE_TRAVEL_POOL = ("LS", "SH")


async def _sights(
    ctx: ToolContext, keywords: list[str], prefixes: list[str], crowd: CrowdPreference
) -> tuple[list[CandidateRow], list[str]]:
    """레포츠·쇼핑은 여행지 풀 밖이라 코드만 걸면 후보가 0곳이 된다."""
    usable: list[str] = []
    dropped: list[str] = []
    for word in keywords:
        codes = await retrieve.resolve_category_codes(ctx.session, [word])
        target = dropped if codes and _outside_pool(codes) else usable
        target.append(word)
    codes = await retrieve.resolve_category_codes(ctx.session, usable)
    rows = await retrieve.search_candidates(
        ctx.session,
        repositories.CandidateQuery(
            limit=retrieve.CANDIDATE_LIMIT, codes=codes or None, region_prefixes=prefixes
        ),
        preference=crowd,
        near=False,
    )
    return rows, dropped


def _outside_pool(codes: list[str]) -> bool:
    return all(code.startswith(OUTSIDE_TRAVEL_POOL) for code in codes)


def _meal_words(keywords: list[str]) -> list[str]:
    return [word for word in keywords if retrieve.food_word([word]) is not None]


def _slots(eating: list[str]) -> list[tuple[str, str, list[str]]]:
    """구체 음식은 각자 풀을 갖는다 — 제목 조건이 AND 라 '국밥 초밥' 은 교집합이 빈다."""
    slots: dict[tuple[str, str], tuple[str, str, list[str]]] = {}
    for word in eating:
        action = retrieve.food_word([word])
        if action is None:
            continue
        dishes = retrieve.dish_search_terms(word) if action == "food" else []
        slots.setdefault((action, dishes[0] if dishes else ""), (word, action, dishes))
    return list(slots.values())


async def _meals(
    ctx: ToolContext, eating: list[str], prefixes: list[str], crowd: CrowdPreference
) -> tuple[list[tuple[str, list[CandidateRow]]], list[str]]:
    """맛집과 카페는 풀이 달라 한 번에 못 뽑는다 — 요청한 종류마다 따로 돌려준다."""
    pools: list[tuple[str, list[CandidateRow]]] = []
    missing: list[str] = []
    for word, action, dishes in _slots(eating):
        found = await retrieve.search_food(
            ctx.session,
            action=action,
            region_prefixes=prefixes,
            preference=crowd,
            title_terms=dishes or None,
        )
        pool = _without_outliers(_placed(found))
        if pool:
            pools.append((word, pool))
        else:
            missing.append(word)
    return pools, missing


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
        return ToolResult(rows=[], observation="regions 가 비었습니다.", fact=_NEEDS_REGION)

    region = hints[0]
    prefixes = await retrieve.resolve_region_prefixes(ctx.session, hints=[region])
    if not prefixes:
        return ToolResult(
            rows=[],
            observation=f"{region}: {_UNKNOWN}",
            fact=_UNKNOWN_FACT.format(region=region),
        )

    keywords = strings(args, "categories", limit=MAX_KEYWORDS)
    eating = _meal_words(keywords)
    crowd = _crowd(args)
    seeing = [word for word in keywords if word not in eating]

    meals, missing = await _meals(ctx, eating, prefixes, crowd)
    found, unsupported = await _sights(ctx, seeing, prefixes, crowd)
    sights = _without_outliers(_placed(found))
    if not sights:
        missing += [word for word in seeing if word not in unsupported]

    return _assemble(
        region,
        sights=sights,
        meals=meals,
        missing=missing,
        unsupported=unsupported,
        days=days_of(args),
    )


def _assemble(
    region: str,
    *,
    sights: list[CandidateRow],
    meals: list[tuple[str, list[CandidateRow]]],
    missing: list[str],
    unsupported: list[str],
    days: int,
) -> ToolResult:
    """맛집은 일정에 끼워 넣는 한 끼다 — 볼거리를 대신하지 않는다.

    볼거리가 아예 없는 지역에서만 첫 음식 풀이 일정의 뼈대가 되고, 나머지 종류는
    그대로 하루 한 자리를 지킨다.
    """
    if not sights and meals:
        sights, meals = (meals[0][1], meals[1:])
    per_meal = min(len(meals), PER_DAY - 1)
    per_day = PER_DAY - per_meal
    ordered = _chain(sights[: days * per_day])
    if not ordered:
        return ToolResult(rows=[], observation=f"{region}: {_EMPTY}")

    left = [(word, list(rows)) for word, rows in meals]
    taken = {row.content_id for row in ordered}
    short: dict[str, None] = {}
    served: set[int] = set()
    lines: list[str] = []
    plan: list[CandidateRow] = []
    for day in range(days):
        leg = ordered[day * per_day : (day + 1) * per_day]
        if not leg:
            break
        picks = [(day * per_meal + slot) % len(left) for slot in range(per_meal)]
        served.update(picks)
        leg = _chain([*leg, *_one_of_each(leg, [left[index] for index in picks], taken, short)])
        plan.extend(leg)
        names = " → ".join(row.title for row in leg)
        lines.append(f"{day + 1}일차: {names} (직선거리 {round(_legs_km(leg))}km)")

    for index, (word, _rows) in enumerate(left):
        if index not in served:
            short[word] = None

    plan_text = f"{region} {len(lines)}일 일정 — " + " / ".join(lines)
    if len(lines) < days:
        plan_text += f" (요청한 {days}일을 채울 곳이 부족해 {len(lines)}일로 줄였습니다)"
    if missing:
        plan_text += f" ({' · '.join(missing)}: 그 지역에서 찾지 못했습니다)"
    if short:
        plan_text += f" ({' · '.join(short)}: 하루 자리가 모자라 일정에 다 넣지 못했습니다)"
    if unsupported:
        plan_text += f" ({' · '.join(unsupported)}: 일정에 넣을 수 있는 종류가 아닙니다)"
    return ToolResult(rows=plan, observation=plan_text, fact=plan_text)


def _one_of_each(
    leg: Sequence[CandidateRow],
    pools: Sequence[tuple[str, list[CandidateRow]]],
    taken: set[str],
    short: dict[str, None],
) -> list[CandidateRow]:
    """종류마다 하루 한 곳씩 — 거리만 보면 모든 날이 식당으로 채워진다.

    맛집 풀과 국밥 풀은 겹친다 — 이미 고른 곳은 모든 풀에서 뺀다.
    """
    picked: list[CandidateRow] = []
    for word, pool in pools:
        chosen = _nearest(leg, [row for row in pool if row.content_id not in taken])
        if chosen is None:
            short[word] = None
            continue
        pool.remove(chosen)
        taken.add(chosen.content_id)
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
                "description": (
                    "넣고 싶은 장소 종류. 비우면 전체. "
                    "관광지와 음식점만 넣을 수 있고 숙소·쇼핑·레포츠는 다루지 않는다."
                ),
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
