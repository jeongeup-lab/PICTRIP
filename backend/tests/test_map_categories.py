from __future__ import annotations

import pytest

from app.modules.spots.services import NearbyCategory, derive_category


@pytest.mark.parametrize(
    "l1,l2,l3,expected",
    [
        ("HS", None, None, "attraction"),
        ("NA", None, None, "attraction"),
        ("EX", None, None, "attraction"),
        ("VE", "VE01", None, "attraction"),
        ("VE", "VE06", None, None),
        ("FD", "FD01", "FD010100", "food"),
        ("FD", "FD03", "FD030100", "cafe"),
        ("FD", "FD05", "FD050100", "cafe"),
        ("LS", "LS01", None, "leisure"),
        ("SH", "SH01", None, "shopping"),
        ("SH", "SH04", None, None),
        ("XX", None, None, None),
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


def test_travel_predicate_keeps_exhibition_and_performance_venues() -> None:
    from app.modules.spots.services import attraction_category_sql, travel_category_sql

    travel = travel_category_sql()
    nearby = attraction_category_sql()

    assert "NOT IN ('VE06', 'VE07', 'VE08', 'VE09', 'VE10', 'VE11')" in nearby
    assert "NOT IN ('VE08', 'VE09', 'VE10', 'VE11')" in travel
    assert "'VE06'" not in travel
    assert "'VE07'" not in travel
    assert "spots.content_type_id != 32" in travel


def test_travel_predicate_keeps_non_ve_and_uncoded_ve_branches() -> None:
    from app.modules.spots.services import travel_category_sql

    travel = travel_category_sql()

    assert "spots.lcls_systm1 IN ('HS', 'NA', 'EX')" in travel
    assert "spots.lcls_systm1 = 'VE'" in travel
    assert "spots.lcls_systm2 IS NULL" in travel
