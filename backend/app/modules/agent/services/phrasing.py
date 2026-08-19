from __future__ import annotations

import re

from app.modules.agent.services import detail as detail_service

METERS_STEP = 10
DISTANCE_TAG = re.compile(r"^\d+(\.\d+)?(km|m)$")


def addr_label(addr1: str | None) -> str:
    if not addr1:
        return ""
    return " ".join(addr1.split()[:2])


def meters_label(meters: float) -> str:
    rounded = max(METERS_STEP, round(meters / METERS_STEP) * METERS_STEP)
    if rounded < 1000:
        return f"{rounded}m"
    return f"{meters / 1000:.1f}km"


def km_label(km: float) -> str:
    return meters_label(km * 1000)


def is_distance_tag(tag: str | None) -> bool:
    return tag is not None and DISTANCE_TAG.match(tag) is not None


def dish_title_condition(title_terms: list[str]) -> str:
    return f"상호에 요청한 음식명({' · '.join(title_terms)})이 모두 들어간 곳"


def subject_particle(word: str) -> str:
    return "이" if detail_service.ends_with_consonant(word) else "가"


def copula(word: str) -> str:
    return "이에요" if detail_service.ends_with_consonant(word) else "예요"
