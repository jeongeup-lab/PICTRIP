from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from app.core.db import AsyncSession
from app.modules.agent.errors import AgentNoResults
from app.modules.agent.repositories import CandidateRow
from app.modules.agent.schemas import AskStep, DropAxis, QueryIntent
from app.modules.agent.services import retrieve
from app.modules.agent.services import suggest as suggest_service

TITLE_AXES: frozenset[DropAxis] = frozenset({"category", "near", "region"})
INDOOR_RETRY_LABEL = "실내로만 다시 조회"


def count(rows: list[CandidateRow]) -> str:
    return f"{len(rows)}곳"


def locatable(rows: list[CandidateRow], *, near: bool) -> list[CandidateRow]:
    if not near:
        return rows
    return [row for row in rows if row.lat is not None and row.lng is not None]


def widen_label(scope: retrieve.RegionScope) -> str:
    return f"{scope.narrowed_label} 결과 없음 — {scope.widened_label}로 넓힘"


def search_label(keywords: list[str], prefixes: list[str], *, indoor: bool) -> str:
    if indoor:
        head = "실내"
    elif keywords:
        head = " · ".join(keywords[:2])
    elif prefixes:
        head = prefixes[0]
    else:
        head = "전국"
    return f"{head} 관광지 조회"


@dataclass
class Ask:
    """한 턴이 검색에 들어가기 직전 상태.

    준비 단계가 채우고 라우트가 읽고 고쳐 쓴다. 갈래마다 같은 계산을 되풀이하지 않게 하려고 둔다.
    """

    session: AsyncSession
    steps: list[AskStep]
    intent: QueryIntent
    scope: retrieve.RegionScope
    category: retrieve.CategoryScope
    prefixes: list[str]
    keywords: list[str]
    mood_ids: list[int]
    pinned: list[CandidateRow]
    lat: float | None
    lng: float | None
    near: bool
    place_only: bool
    title_only: bool

    candidates: list[CandidateRow] = field(default_factory=list)
    widened: retrieve.RegionScope | None = None
    axes: frozenset[DropAxis] = suggest_service.ALL_AXES
    searched_codes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.searched_codes = self.codes

    @property
    def codes(self) -> list[str]:
        return self.category.codes

    @property
    def needs_a_wider_region(self) -> bool:
        return (
            not locatable(self.candidates, near=self.near)
            and not self.pinned
            and self.scope.widenable
        )

    def widen(self) -> None:
        self.prefixes = self.scope.sido_prefixes
        self.widened = self.scope
        self.intent = self.intent.model_copy(update={"regionHints": list(self.scope.sido_prefixes)})

    async def search(
        self, codes: list[str], prefixes: list[str], *, with_near: bool | None = None
    ) -> list[CandidateRow]:
        return await retrieve.search_candidates(
            self.session,
            codes=codes,
            region_prefixes=prefixes,
            preference=self.intent.crowdPreference,
            lat=self.lat,
            lng=self.lng,
            near=self.near if with_near is None else with_near,
            indoor_only=self.intent.indoorOnly,
            mood_ids=self.mood_ids,
        )


Route = Callable[[Ask], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class Choice:
    """어느 검색을 태울지. 조건과 실행을 한 자리에 묶어 if 사슬을 없앤다."""

    name: str
    when: Callable[[Ask], bool]
    run: Route


async def _only_the_named_place(ask: Ask) -> None:
    if not ask.pinned:
        raise AgentNoResults()
    ask.candidates = []


async def _by_title(ask: Ask) -> None:
    ask.axes = TITLE_AXES
    ask.candidates = await retrieve.search_by_title(
        ask.session, ask.keywords, region_prefixes=ask.prefixes
    )
    ask.steps.append(
        AskStep(
            tool="title_search",
            label=f"{ask.keywords[0]} 이름으로 조회",
            badge=count(ask.candidates),
        )
    )
    if not ask.needs_a_wider_region:
        return
    ask.widen()
    ask.candidates = await retrieve.search_by_title(
        ask.session, ask.keywords, region_prefixes=ask.prefixes
    )
    ask.steps.append(
        AskStep(tool="title_search", label=widen_label(ask.scope), badge=count(ask.candidates))
    )


async def _by_category(ask: Ask) -> None:
    ask.candidates = await ask.search(ask.searched_codes, ask.prefixes)
    ask.steps.append(
        AskStep(
            tool="category_search",
            label=search_label(ask.keywords, ask.prefixes, indoor=ask.intent.indoorOnly),
            badge=count(ask.candidates),
        )
    )
    if ask.needs_a_wider_region:
        widened_codes = ask.codes
        ask.widen()
        ask.candidates = await ask.search(widened_codes, ask.prefixes)
        ask.steps.append(
            AskStep(
                tool="category_search",
                label=widen_label(ask.scope),
                badge=count(ask.candidates),
            )
        )
    if not ask.candidates and ask.intent.indoorOnly and ask.codes:
        ask.searched_codes = []
        ask.candidates = await ask.search(ask.searched_codes, ask.prefixes)
        ask.intent = ask.intent.model_copy(update={"categoryKeywords": []})
        ask.steps.append(
            AskStep(
                tool="category_search",
                label=INDOOR_RETRY_LABEL,
                badge=count(ask.candidates),
            )
        )
    if ask.mood_ids and ask.candidates:
        ask.steps.append(
            AskStep(tool="mood_search", label="분위기로 추림", badge=count(ask.candidates))
        )


SEARCHES: tuple[Choice, ...] = (
    Choice("place_only", lambda ask: ask.place_only, _only_the_named_place),
    Choice("title_only", lambda ask: ask.title_only, _by_title),
    Choice("category", lambda _ask: True, _by_category),
)


def pick(table: tuple[Choice, ...], ask: Ask) -> Choice:
    for choice in table:
        if choice.when(ask):
            return choice
    return table[-1]


async def run_search(ask: Ask) -> None:
    await pick(SEARCHES, ask).run(ask)
