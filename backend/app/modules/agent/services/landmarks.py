from __future__ import annotations

LANDMARK_SUFFIXES = ("역", "터미널", "공항")
NOT_LANDMARK_WORDS = frozenset(
    {"지역", "구역", "유역", "권역", "해역", "영역", "전역", "광역", "역세권"}
)
NOT_LANDMARK_SUFFIXES = ("지역",)
MIN_LANDMARK_CHARS = 3


def is_landmark(token: str) -> bool:
    if len(token) < MIN_LANDMARK_CHARS or token in NOT_LANDMARK_WORDS:
        return False
    if token.endswith(NOT_LANDMARK_SUFFIXES):
        return False
    return token.endswith(LANDMARK_SUFFIXES)
