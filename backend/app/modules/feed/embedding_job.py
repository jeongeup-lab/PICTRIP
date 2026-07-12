from __future__ import annotations

import asyncio

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.db import async_session_factory
from app.core.embedding import embedder
from app.core.logging import get_logger

logger = get_logger(__name__)

_embed_lock = asyncio.Lock()

_USER_AGENT = "PicTrip/1.0 (https://pictrip.org)"

_TARGETS_SQL = "SELECT id, image_url FROM overseas_spots WHERE embedding IS NULL ORDER BY id"
_WRITE_SQL = text(
    "UPDATE overseas_spots SET embedding = CAST(:emb AS halfvec(512)), "
    "updated_at = now() WHERE id = :oid"
)


async def collect_overseas_targets(
    session: AsyncSession, *, limit: int | None = None
) -> list[tuple[int, str]]:
    sql, params = _TARGETS_SQL, {}
    if limit:
        sql += " LIMIT :limit"
        params = {"limit": limit}
    rows = (await session.execute(text(sql), params)).all()
    return [(int(oid), url) for oid, url in rows]


async def _embed_one(
    oid: int, image_url: str, client: httpx.AsyncClient, dl_sem: asyncio.Semaphore
) -> tuple[int, list[float] | None]:
    try:
        async with dl_sem:
            resp = await client.get(image_url, timeout=20.0, follow_redirects=True)
        if resp.status_code != 200 or not resp.content:
            logger.warning(
                "overseas.embed.download_failed", overseas_id=oid, status=resp.status_code
            )
            return (oid, None)
        async with _embed_lock:
            vector = await asyncio.to_thread(embedder.embed_image, resp.content)
        return (oid, vector)
    except Exception as exc:
        logger.warning("overseas.embed.failed", overseas_id=oid, error=str(exc))
        return (oid, None)


async def run_overseas_embedding_job(
    *,
    limit: int | None = None,
    concurrency: int = 8,
    batch_size: int = 50,
    session_factory: async_sessionmaker[AsyncSession] = async_session_factory,
) -> dict[str, int]:
    async with session_factory() as session:
        targets = await collect_overseas_targets(session, limit=limit)
    counters = {"targets": len(targets), "embedded": 0, "failed": 0}
    logger.info("overseas.embed.start", targets=len(targets))
    if not targets:
        return counters

    dl_sem = asyncio.Semaphore(max(1, concurrency))
    async with httpx.AsyncClient(headers={"User-Agent": _USER_AGENT}) as client:
        for i in range(0, len(targets), max(1, batch_size)):
            batch = targets[i : i + max(1, batch_size)]
            outcomes = await asyncio.gather(
                *(_embed_one(oid, url, client, dl_sem) for oid, url in batch)
            )
            async with session_factory() as session:
                for oid, vector in outcomes:
                    if vector is None:
                        counters["failed"] += 1
                        continue
                    literal = "[" + ",".join(f"{v:.8f}" for v in vector) + "]"
                    await session.execute(_WRITE_SQL, {"emb": literal, "oid": oid})
                    counters["embedded"] += 1
                await session.commit()
    logger.info(
        "overseas.embed.done",
        targets=counters["targets"],
        embedded=counters["embedded"],
        failed=counters["failed"],
    )
    return counters
