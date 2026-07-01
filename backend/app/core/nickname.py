"""Random Korean nickname generator — assigned to ``users.name`` at account creation.

Travel/nature themed, wholesome, all-Korean. Result is ``{형용사}{명사}{번호}`` and
always fits ``users.name`` (VARCHAR(50)). Pass ``rng`` for deterministic tests."""

from __future__ import annotations

import random

# Travel / nature / mood adjectives (wholesome). >= 20.
_ADJECTIVES: tuple[str, ...] = (
    "포근한",
    "잔잔한",
    "설레는",
    "따스한",
    "청량한",
    "고요한",
    "싱그러운",
    "느긋한",
    "새로운",
    "반짝이는",
    "다정한",
    "산뜻한",
    "빛나는",
    "향긋한",
    "낭만적인",
    "푸른",
    "맑은",
    "달콤한",
    "포근포근",
    "선선한",
    "명랑한",
    "온화한",
)

# Travel / nature nouns (wholesome). >= 20.
_NOUNS: tuple[str, ...] = (
    "여행자",
    "나그네",
    "바닷가",
    "노을",
    "산책자",
    "구름",
    "파도",
    "별빛",
    "바람",
    "오솔길",
    "등대",
    "물결",
    "언덕",
    "숲길",
    "골목",
    "섬마을",
    "들꽃",
    "새벽",
    "달빛",
    "여울",
    "봉우리",
    "호수",
)


def generate_nickname(rng: random.Random | None = None) -> str:
    """Return a random Korean nickname like ``포근한여행자42``.

    Length is always <= 50 (longest possible combination is well under the
    ``users.name`` column limit). ``rng`` lets tests seed a deterministic
    ``random.Random`` instead of the module-global generator."""
    r = rng if rng is not None else random
    adjective = r.choice(_ADJECTIVES)
    noun = r.choice(_NOUNS)
    number = r.randint(10, 999)  # 2-3 digits
    return f"{adjective}{noun}{number}"
