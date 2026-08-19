from __future__ import annotations

import pytest

from app.modules.feed.services.matching import (
    MatchRow,
    _cache_get,
    _cache_set,
    invalidate_all_match_cache,
    invalidate_match_cache,
)


async def test_invalidate_all_match_cache_advances_revision(redis_client_fake) -> None:
    await redis_client_fake.set("match:0:1", "cached")
    await redis_client_fake.set("spot:1", "preserved")

    revision = await invalidate_all_match_cache(redis_client_fake)

    assert revision == 1
    assert await redis_client_fake.get("matching:revision") == "1"
    assert await redis_client_fake.get("match:0:1") == "cached"
    assert await redis_client_fake.get("spot:1") == "preserved"


async def test_invalidate_all_match_cache_fails_open(
    redis_client_fake, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def broken_incr(*args: object, **kwargs: object) -> int:
        raise ConnectionError("redis unavailable")

    monkeypatch.setattr(redis_client_fake, "incr", broken_incr)

    assert await invalidate_all_match_cache(redis_client_fake) == 0


async def test_per_id_invalidation_drops_only_that_key(redis_client_fake) -> None:
    """한 건 무효화가 리비전을 올리면 나머지 스팟 캐시까지 통째로 버려진다."""
    await redis_client_fake.set("matching:revision", 7)
    await redis_client_fake.set("match:7:42", "cached")
    await redis_client_fake.set("match:7:99", "other")

    await invalidate_match_cache(redis_client_fake, overseas_id=42)

    assert await redis_client_fake.get("matching:revision") == "7"
    assert await redis_client_fake.get("match:7:42") is None
    assert await redis_client_fake.get("match:7:99") == "other"


async def test_in_flight_old_generation_write_is_not_visible(redis_client_fake) -> None:
    row = MatchRow(
        content_id="spot-1",
        title="title",
        region_label="Seoul",
        image_url="https://image/old.jpg",
        overview_first=None,
    )
    captured_revision = 0

    active_revision = await invalidate_all_match_cache(redis_client_fake)
    await _cache_set(redis_client_fake, captured_revision, 42, [row])

    assert await redis_client_fake.get("match:0:42") is not None
    assert await _cache_get(redis_client_fake, active_revision, 42) is None
