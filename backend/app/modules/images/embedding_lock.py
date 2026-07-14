from __future__ import annotations

from redis.asyncio import Redis
from redis.asyncio.lock import Lock

EMBEDDING_JOB_LOCK_NAME = "admin:embed:running"
EMBEDDING_JOB_LOCK_TTL_SECONDS = 4 * 3600
EmbeddingJobLock = Lock


async def acquire_embedding_job_lock(redis: Redis) -> EmbeddingJobLock | None:
    lock = redis.lock(
        EMBEDDING_JOB_LOCK_NAME,
        timeout=EMBEDDING_JOB_LOCK_TTL_SECONDS,
        blocking_timeout=0,
        thread_local=False,
    )
    return lock if await lock.acquire(blocking=False) else None


async def release_embedding_job_lock(lock: EmbeddingJobLock) -> None:
    await lock.release()
