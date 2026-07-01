"""Unit tests for the random Korean nickname generator (app.core.nickname)."""

from __future__ import annotations

import random

from app.core.nickname import generate_nickname


def test_generate_nickname_non_empty_and_fits_column() -> None:
    for _ in range(200):
        nick = generate_nickname()
        assert nick  # non-empty
        assert len(nick) <= 50  # fits users.name VARCHAR(50)


def test_generate_nickname_seeded_is_deterministic() -> None:
    a = generate_nickname(random.Random(42))
    b = generate_nickname(random.Random(42))
    assert a == b


def test_generate_nickname_varies_across_seeds() -> None:
    samples = {generate_nickname(random.Random(seed)) for seed in range(50)}
    # Distinct seeds should yield varied output (collisions are rare).
    assert len(samples) > 1
