"""주간 큐레이션 편성표 — 어떤 지역을 어떤 구성으로 보여줄지."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.modules.spots.categories import NearbyCategory

KICKER = "이번 주 큐레이션"


@dataclass(frozen=True)
class Slot:
    category: NearbyCategory
    count: int


@dataclass(frozen=True)
class Program:
    sigungu: str
    title: str
    lead: str
    slots: tuple[Slot, ...]

    @property
    def size(self) -> int:
        return sum(slot.count for slot in self.slots)


_COURSE = (
    Slot(NearbyCategory.attraction, 2),
    Slot(NearbyCategory.food, 2),
    Slot(NearbyCategory.cafe, 2),
)

PROGRAMS = (
    Program(
        sigungu="정읍시",
        title="정읍, 저수지 끼고 한 바퀴",
        lead="물가에서 시작해 한우와 찻집으로 닫는 하루.",
        slots=_COURSE,
    ),
)


def program_for(today: date) -> Program:
    return PROGRAMS[today.isocalendar().week % len(PROGRAMS)]


def subtitle(program: Program, found: int) -> str:
    return f"{program.sigungu} {found}곳. {program.lead}"
