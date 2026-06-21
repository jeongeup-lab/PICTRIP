"""SSOT 카테고리 파생 규칙 (spec §3). DB 불필요 — 순수 함수."""

from __future__ import annotations

import pytest

from app.modules.spots.services import NearbyCategory, derive_category


@pytest.mark.parametrize(
    "l1,l2,l3,expected",
    [
        ("HS", None, None, "attraction"),
        ("NA", None, None, "attraction"),
        ("EX", None, None, "attraction"),
        ("VE", "VE01", None, "attraction"),  # VE, 제외코드 아님 → 관광
        ("VE", "VE06", None, None),  # VE06~VE11 제외 → 관광 아님
        ("FD", "FD01", "FD010100", "food"),  # 음식점
        ("FD", "FD03", "FD030100", "cafe"),  # 제과(FD030100)는 카페 (food보다 우선)
        ("FD", "FD05", "FD050100", "cafe"),  # 카페
        ("LS", "LS01", None, "leisure"),  # 레저
        ("SH", "SH01", None, "shopping"),  # 쇼핑
        ("SH", "SH04", None, None),  # 면세점 제외
        ("XX", None, None, None),  # 미분류
    ],
)
def test_derive_category(l1, l2, l3, expected):
    assert derive_category(l1, l2, l3) == expected


def test_enum_values():
    assert {c.value for c in NearbyCategory} == {
        "attraction",
        "food",
        "cafe",
        "leisure",
        "shopping",
    }
