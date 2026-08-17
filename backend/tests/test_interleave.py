from __future__ import annotations

from app.modules.feed.services.interleave import NEARBY_PATTERN, TRENDING_PATTERN, interleave


def test_follows_the_pattern_when_every_pool_is_full() -> None:
    pools = {
        "spot": ["s1", "s2", "s3", "s4"],
        "cafe": ["c1", "c2", "c3"],
        "food": ["f1", "f2"],
        "festa": ["e1"],
    }
    out = interleave(pools, TRENDING_PATTERN, limit=10, key_of=lambda x: x)
    assert out == ["s1", "c1", "s2", "f1", "s3", "c2", "e1", "s4", "c3", "f2"]


def test_backfills_from_other_pools_when_one_runs_dry() -> None:
    pools = {"spot": ["s1"], "cafe": ["c1", "c2", "c3"], "food": [], "festa": []}
    out = interleave(pools, TRENDING_PATTERN, limit=4, key_of=lambda x: x)
    assert out == ["s1", "c1", "c2", "c3"]


def test_deduplicates_items_shared_between_pools() -> None:
    pools = {"spot": ["dup", "s2"], "cafe": ["dup", "c2"], "food": [], "festa": []}
    out = interleave(pools, TRENDING_PATTERN, limit=4, key_of=lambda x: x)
    assert out == ["dup", "c2", "s2"]


def test_respects_the_limit() -> None:
    pools = {"spot": list("abcdefgh"), "cafe": [], "food": [], "festa": []}
    out = interleave(pools, NEARBY_PATTERN, limit=3, key_of=lambda x: x)
    assert len(out) == 3


def test_empty_pools_yield_empty_ranking() -> None:
    assert interleave({"spot": []}, TRENDING_PATTERN, limit=10, key_of=lambda x: x) == []
