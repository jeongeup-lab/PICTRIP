"""Category derivation rules (spec §3) — pure function, no DB."""

from __future__ import annotations

import pytest

from app.modules.spots.services import NearbyCategory, derive_category


@pytest.mark.parametrize(
    "l1,l2,l3,expected",
    [
        ("HS", None, None, "attraction"),
        ("NA", None, None, "attraction"),
        ("EX", None, None, "attraction"),
        ("VE", "VE01", None, "attraction"),  # not an excluded code
        ("VE", "VE06", None, None),  # VE06~VE11 excluded
        ("FD", "FD01", "FD010100", "food"),
        ("FD", "FD03", "FD030100", "cafe"),  # bakery FD030100 → cafe, takes priority over food
        ("FD", "FD05", "FD050100", "cafe"),
        ("LS", "LS01", None, "leisure"),
        ("SH", "SH01", None, "shopping"),
        ("SH", "SH04", None, None),  # duty-free excluded
        ("XX", None, None, None),  # unclassified
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
