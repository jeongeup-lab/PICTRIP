"""Unit tests for the random Korean nickname generator (app.modules.users.nickname)."""

from __future__ import annotations

import random

from app.modules.users.nickname import generate_nickname


def test_generate_nickname_non_empty_and_fits_column() -> None:
    for _ in range(200):
        nick = generate_nickname()
        assert nick
        assert len(nick) <= 50


def test_generate_nickname_seeded_is_deterministic() -> None:
    a = generate_nickname(random.Random(42))
    b = generate_nickname(random.Random(42))
    assert a == b


def test_generate_nickname_varies_across_seeds() -> None:
    samples = {generate_nickname(random.Random(seed)) for seed in range(50)}
    assert len(samples) > 1
