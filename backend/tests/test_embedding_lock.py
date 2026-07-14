from __future__ import annotations

import pytest
from redis.exceptions import LockNotOwnedError

from app.modules.images.embedding_lock import (
    EMBEDDING_JOB_LOCK_NAME,
    acquire_embedding_job_lock,
    release_embedding_job_lock,
)


async def test_embedding_job_lock_is_exclusive_and_owner_safe(redis_client_fake) -> None:
    first = await acquire_embedding_job_lock(redis_client_fake)
    assert first is not None
    assert await acquire_embedding_job_lock(redis_client_fake) is None

    await redis_client_fake.set(EMBEDDING_JOB_LOCK_NAME, "replacement")
    with pytest.raises(LockNotOwnedError):
        await release_embedding_job_lock(first)
    assert await redis_client_fake.get(EMBEDDING_JOB_LOCK_NAME) == "replacement"

    await redis_client_fake.delete(EMBEDDING_JOB_LOCK_NAME)
    second = await acquire_embedding_job_lock(redis_client_fake)
    assert second is not None
    await release_embedding_job_lock(second)
    assert await redis_client_fake.exists(EMBEDDING_JOB_LOCK_NAME) == 0
